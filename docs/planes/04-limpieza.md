# Plan 04 — Limpieza de `drop/` (SQL numerado + tests + auditoría + pipeline)

## Contexto
El perfilado (paso 03, `docs/perfilado.md`) y las decisiones D-09 a D-18 ya fijaron cómo limpiar. Falta el código: la ingesta de R4 que unifica los dos formatos, convierte °F, deduplica y normaliza IDs, con controles que **frenan** el pipeline y un cuadre de filas auditable (R4a: crudas = limpias + duplicados + inválidas). Resultado: `make run` deja las tablas limpias en `salida/` y corta con código ≠ 0 si una regla se rompe. `drop/` no se toca (solo `read_csv` / `read_text`).

## Estructura
```
sql/                      # se ejecutan en orden; cada uno crea tablas en salida/limpieza.duckdb
  01_crudo.sql            # vistas sobre drop/ + macro normalizar_id + tabla de encabezados
  02_equipos.sql          # maestro tipado
  03_lecturas_unificadas.sql  # unifica formatos, castea, convierte °F, asigna motivo de descarte
  04_lecturas_limpias.sql # filtra inválidas y deduplica (D-10) → tabla lecturas
  05_ot.sql               # OT: ID normalizado (D-17), tipo normalizado (D-18), fechas
  06_auditoria.sql        # auditoria (resumen) + descartes (detalle fila a fila)
  07_exportar.sql         # COPY a salida/*.parquet y salida/auditoria.csv
tests/                    # cada archivo devuelve las filas que rompen la regla; vacío = pasa
  01_encabezados_conocidos.sql   # D-09
  03_unidad_temp_conocida.sql    # D-12
  04_sin_duplicados.sql          # R4b: 0 repetidos por (equipo, ts)
  04_temp_c_en_rango.sql         # °C plausible (ver decisión pendiente 2)
  04_ids_en_maestro.sql          # toda lectura cruza con equipos
  05_ot_ids_en_maestro.sql       # toda OT conservada cruza con equipos
  06_cuadre.sql                  # por fuente: entran = quedan + Σ salen (R4a)
pipeline.py
Makefile
```
**Convención:** el prefijo numérico del test indica después de qué paso SQL corre. Así el pipeline se corta en el paso donde aparece el problema (p. ej. un encabezado desconocido frena antes de unificar nada).

## Detalle por archivo

**01_crudo.sql** (reutiliza las vistas de `docs/perfilado.md`, sección Preparación)
- `raw_lecturas`: `read_csv(getvariable('drop_dir') || '/lecturas-*.csv', union_by_name=true, filename=true, all_varchar=true)`. Igual para `raw_equipos` y `raw_ot`.
- `encabezados`: `read_text(.../lecturas-*.csv)` → `filename, rtrim(split_part(content, chr(10), 1), chr(13))` (los encabezados traen `\r`; verificado).
- `CREATE MACRO normalizar_id(x) AS upper(regexp_replace(trim(x), '^(?i)eq-?', 'EQ-'))` (la misma regla de H-13), que se aplica a lecturas, maestro y OT.

**03_lecturas_unificadas.sql** → tabla `lecturas_staging`, una fila por fila cruda:
`archivo, formato ('viejo'|'nuevo'), equipo_crudo, equipment_id (normalizado), ts, vib_mm_s, temp_crudo, unidad_temp, temp_c, motivo_descarte`.
- `coalesce` de las columnas viejo/nuevo (D-09); `TRY_CAST` a TIMESTAMP/DOUBLE (acepta los dos formatos de ts).
- `temp_c`: `C` o formato viejo → tal cual; `F` → (F−32)·5/9; cualquier otra unidad → NULL (y la frena el test 03).
- `motivo_descarte`: un `CASE` en cascada (el primero que aplica): `ts_invalido` → `valor_no_numerico` → `equipo_fuera_del_maestro` (D-11). Hoy solo se activa el último (48 filas de EQ-TEST-01).

**04_lecturas_limpias.sql** → tabla `lecturas` (`equipment_id, ts, vib_mm_s, temp_c, formato, archivo`):
- entre las filas sin motivo, `ROW_NUMBER() OVER (PARTITION BY equipment_id, ts ORDER BY vib_mm_s DESC, archivo, temp_c)` = 1 (D-10). El desempate extra hace el resultado determinista (R1).
- `lecturas_duplicadas`: las filas con rn > 1, para la auditoría.

**05_ot.sql** → tabla `ot` (`nro_ot, equipo_crudo, equipment_id, fecha_apertura, fecha_cierre, tipo_crudo, tipo, descripcion`)
- `tipo`: PREV/Preventivo → `preventivo`; CORR/Correctivo → `correctivo`; vacío → `sin_tipo`; cualquier otro → `desconocido` (se reporta y no frena el pipeline, porque el tipo no decide fallas, D-18).
- Fechas: `TRY_STRPTIME(..., '%d/%m/%Y %H:%M')`.
- Descarte con motivo: `equipo_fuera_del_maestro` (D-17, hoy 0) y `fecha_invalida` (hoy 0). Las OT descartadas van a `ot_descartadas`.
- La clasificación de fallas (D-20) queda **fuera de este paso**: es un parámetro del criterio y va con su archivo de configuración.

**06_auditoria.sql**
- `auditoria` (resumen): `fuente, concepto ('entran'|'salen'|'quedan'), motivo, filas`. Por ejemplo, para lecturas: entran 115.065; salen 229 por `duplicado`; salen 48 por `equipo_fuera_del_maestro`; quedan 114.788. También informativos: `ids_normalizados` (lecturas 0, OT 17) y `temp_convertida_de_F` (11.400).
- `descartes` (detalle): `fuente, archivo/nro_ot, equipo_crudo, ts, motivo`, una fila por cada fila que sale. Responde a "cuáles" (D-11, D-17).

**Tests**: cada uno es un `SELECT` que devuelve las filas culpables. Ejemplos:
- `04_sin_duplicados`: `SELECT equipment_id, ts, count(*) FROM lecturas GROUP BY ALL HAVING count(*) > 1`.
- `04_ids_en_maestro`: `SELECT DISTINCT equipment_id FROM lecturas ANTI JOIN equipos USING (equipment_id)`.
- `06_cuadre`: por fuente, `entran − quedan − Σ salen <> 0`.

**pipeline.py** (~60 líneas, sin red)
- `DROP_DIR` por variable de entorno (por defecto `drop`, R10) → `SET VARIABLE drop_dir`. Antes de arrancar verifica que la ruta exista.
- Borra y recrea `salida/limpieza.duckdb` (corridas idempotentes) y fija `SET threads=1` (orden repetible, igual que en `docs/herramientas/perfilado.py`).
- Para cada `sql/NN_*.sql` en orden: lo ejecuta y después corre los `tests/NN_*.sql`. Si un test devuelve filas, imprime el paso, el test y hasta 10 filas culpables, y sale con `sys.exit(1)`. Al final imprime la tabla `auditoria`.
- Para separar sentencias reutiliza `dividir()` de `docs/herramientas/perfilado.py` (copiada, no importada desde docs/).

**Makefile**: `run: ; uv run --locked python pipeline.py`, más `clean` (borra `salida/`) y `.PHONY`.

## Decisiones confirmadas por el usuario (se registran en DECISIONES.md)
1. **D-22 · Filas con ts o valores que no se pueden leer** (hoy 0, H-05): se descartan con motivo y se cuentan (R4a: "inválidas descartadas"); no frenan el pipeline. Descartado: frenar (un dato roto bloquearía todo el mes).
2. **D-23 · Rango del test "°C en rango": [0, 120] °C.** De dónde sale cada borde:
   - 120 queda por encima del umbral más alto del maestro (110 °C, turbina) y del máximo real del mes (95,8 °C), y por debajo del mínimo °F sin convertir que se observó (126,7).
   - 0 es el piso físico para equipos rotativos en operación (el mínimo real es 52,6 °C).
   - Descartados: techo 150 (dejaría pasar °F sin convertir entre 126 y 150) y techo 110 (podría frenar con una turbina recalentada real). Límite: un equipo que opere a menos de 49 °C, sin convertir, quedaría debajo de 120 y no se detectaría.
3. **D-24 · Formato de salida**: `salida/limpieza.duckdb` más `lecturas.parquet`, `equipos.parquet`, `ot.parquet` y `auditoria.csv`.
4. **D-25 · Registro de corridas para observabilidad**: `salida/corridas.csv`, que se acumula (no se reescribe) con una fila por paso SQL y por test en cada corrida:
   `id_corrida` (timestamp de inicio), `drop_dir`, `orden`, `tipo` (`sql`|`test`), `nombre` (archivo), `estado` (`ok`|`fallo`|`error`|`no_corrio`), `filas` (filas creadas o filas culpables), `duracion_s`, `mensaje` (primera fila culpable o el error).
   - Si el pipeline se corta, los pasos restantes quedan como `no_corrio`, para ver dónde se bloqueó.
   - El tablero de observabilidad no se construye ahora: queda en la sección de Escalado de `DECISIONES.md` y se arma sobre este CSV si se pide.
   - `make clean` borra `salida/` y, con ella, el historial. Queda dicho en el README.

## Fuera de alcance (pasos siguientes)
Regla de falla D-20 y su archivo de config; desfase horario D-13; test R4(c) de la tolerancia D-15; `salida/perfilado.md` (R3); `make test`.

## Archivos
Nuevos: `sql/*.sql`, `tests/*.sql`, `pipeline.py`, `Makefile`, `docs/planes/04-limpieza.md` (copia de este plan, como el 03). Se actualiza `DECISIONES.md` (D-22 a D-25). Un commit al cerrar: `feat: limpieza de lecturas, maestro y OT con tests y auditoría`.

## Verificación
1. `make run` → código 0. La auditoría muestra para lecturas 115.065 = 114.788 + 229 + 48 (cifras del perfilado) y para OT 86 entran = 86 quedan, con 17 IDs normalizados. Tipos de OT: 61 / 5 / 20.
2. `git status --porcelain drop/` vacío (R2).
3. Prueba de que el corte funciona: copiar `drop/` al scratchpad, romper una cosa por vez (una fila con unidad `K`, un encabezado renombrado, una fila duplicada del sistema nuevo con `ts` repetido) y correr `DROP_DIR=<copia> uv run python pipeline.py`. Esperado: sale con 1, nombra el test correcto y muestra la fila culpable.
4. Dos corridas seguidas dan el mismo `shasum salida/auditoria.csv`.
5. `corridas.csv`: tras la corrida OK, todas las filas en `ok`. Tras la prueba rota del punto 3, el test culpable aparece en `fallo` y los pasos siguientes en `no_corrio`.
6. Prueba del cuadre: en la copia rota, borrar filas buenas de un CSV no alcanza, porque el cuadre se calcula sobre lo que entra. Lo que se simula es un error interno: se edita temporalmente `04_lecturas_limpias.sql` para que pierda filas, y `06_cuadre` tiene que cortar el pipeline. Después se revierte el cambio.
