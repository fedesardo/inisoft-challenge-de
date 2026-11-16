# Plan 03 — Perfilado de `drop/` con DuckDB

## Contexto
SPEC R3 dice que no hay diccionario de datos y que las decisiones siguientes (qué es una falla, tolerancia de R4, meta de R6) dependen de lo que descubramos. El **perfilado** (*data profiling*) es la inspección sistemática de datos crudos para conocer su estructura, calidad y distribución *antes* de transformarlos. Resultado: `docs/perfilado.md`, con cada hallazgo numerado (H-01, H-02…) junto a la consulta SQL que lo produjo. Así cada afirmación es reproducible.

Este paso **no decide nada**: solo observa. Las decisiones (falla, tolerancia, conversión °F) van después a `DECISIONES.md`, citando el número de hallazgo.

## Reglas que se respetan
- `drop/` solo lectura: DuckDB lee con `read_csv(...)`; nunca escribe ahí. Se verifica al final con `git status --porcelain drop/`.
- Todo en SQL de DuckDB (pandas no hace falta). Sin red ni LLM.
- Consultas ad hoc en el scratchpad; solo se versiona `docs/perfilado.md` (+ este plan). El `salida/perfilado.md` automático de R3 es otro paso posterior y reutilizará estas consultas.

## Método (conceptos que se aplican)
- **union_by_name**: DuckDB une CSV con encabezados distintos alineando por nombre de columna, no por posición; las columnas ausentes quedan en NULL. Con dos formatos esto produce dos juegos de columnas paralelas (`equipment_id`/`asset_id`, etc.) y NULL cruzado, lo cual *es* la evidencia del cambio de formato.
- **filename=true**: agrega la columna con el archivo de origen, para atribuir cada fila a su día/formato y detectar filas cuyo `ts` no coincide con su archivo.
- **Lectura con `all_varchar=true`** primero: evita que DuckDB infiera tipos y oculte valores sucios (p. ej. un "N/A" en una columna numérica); luego se castea con `TRY_CAST` para contar lo que no convierte.
- **Duplicado**: misma clave natural (equipo, timestamp). Se distingue *duplicado exacto* (mismos valores) de *conflictivo* (misma clave, valores distintos), porque se tratan distinto.

## Consultas por área (cada una = un hallazgo H-NN)

**A. Lecturas — estructura**
1. Archivos por formato (agrupar por encabezado) y fecha del primer archivo nuevo. Esperado según lo visto: 10 viejos + 20 nuevos, cambio el 11/02 (confirmar).
2. Filas por día (y por archivo) y por equipo; equipos distintos vs. los 40 del maestro; equipos en lecturas que no están en `equipos.csv` (y formatos de ID: `EQ-101` vs `EQ211`, mayúsculas, espacios).
3. Filas por equipo *por formato* (¿algún equipo cambia de cantidad tras el 11/02?).

**B. Calidad**
4. Duplicados por (equipo, ts) en cada sistema, separados en exactos y conflictivos; confirmar la afirmación del cliente de que vienen solo del viejo (SPEC Asunción).
5. Nulos por columna, por formato.
6. Valores no numéricos (`TRY_CAST` falla) y timestamps que no parsean.

**C. Unidades, rangos, zona horaria**
7. `unidad_temp`: valores distintos y conteos (C/F/otros/NULL) por día y por equipo. Las filas °F: ¿son equipos enteros o filas sueltas?
8. Rangos (mín/máx/percentiles) de vibración y temperatura por formato y por unidad; comprobar que las °F, convertidas con (F−32)·5/9, caen en el rango de las °C (prueba de que son realmente °F). Valores imposibles (negativos, sentinelas tipo −999).
9. Zona horaria: formato del timestamp (`2026-02-01 19:15:00` vs `2026-02-11T05:30:00`; ¿sufijo Z/offset?). Distribución por hora del día por formato (el ciclo diario de temperatura debería caer a la misma hora; un corrimiento de N horas delata UTC vs. local). Granularidad: ¿todo en múltiplos de 15 min?
10. Huecos: esperado 96 lecturas/día/equipo; contar los (equipo, día) con menos, ubicar huecos largos con `LAG(ts)` > 15 min, y días con menos de 40 equipos (los archivos del 09/02 y 16/02 pesan algo menos: sospecha).

**D. Cambio de sistema (por equipo)**
11. Por equipo: media (y mediana, que es robusta a atípicos) de vibración y temperatura *antes* vs. *después* del 11/02, con diferencia y relación. Se calcula crudo y con °F convertido, para ver cuánto del salto es solo unidad. Ordenar por |diferencia| y resumir cuántos equipos exceden, por ejemplo, 10 %. Esto alimenta la tolerancia (PENDIENTE de R4).

**E. Maestro `equipos.csv`**
12. 40 filas, IDs únicos, tipos y plantas, nulos.
13. Unidades de umbrales: rangos de `umbral_temp_c` (¿°C plausible?) y `umbral_vib_mm_s` contra los rangos de las lecturas (p. ej. umbral de temperatura de 85–95 contra máximos observados; qué fracción de lecturas ya supera el umbral, por equipo, antes y después del cambio — si tras el cambio sube mucho, es señal de unidad o escala).

**F. Órdenes de trabajo**
14. Tipos distintos y conteos (`PREV`, `Preventivo`, `CORR`, `Correctivo`, vacío…), normalización de mayúsculas/espacios.
15. Parseo de `fecha_apertura`/`fecha_cierre` (`dd/mm/yyyy hh:mm`); apertura > cierre; nulos.
16. Fechas contra el rango de lecturas (mín/máx de `ts`): OT fuera de rango; OT en las últimas 7 días (no tienen ventana de futuro para evaluar).
17. IDs de equipo en OT que no cruzan con el maestro: crudo vs. normalizado (`upper(replace(trim(...)))` + reinsertar guion). Distinguir los que se arreglan solo con normalizar de los que no existen (¿EQ999?).
18. OT sin tipo: cuántas, y qué dice `descripcion` (muestra y palabras clave de avería: falla, rotura, parada, cambio de rodamiento…); OT duplicadas por `nro_ot`. Solo se describe; la regla de falla es decisión posterior.
19. OT por equipo, y equipos con 2+ correctivos/candidatas a falla.

## Formato de `docs/perfilado.md`
- Encabezado: fecha, DuckDB 2.0.0, nota "datos crudos, solo lectura".
- Resumen ejecutivo (tabla de hallazgos: nº, qué, magnitud, impacto en decisiones).
- Una sección por hallazgo: **H-NN título** → *Consulta* (bloque `sql`) → *Resultado* (tabla breve/cifra) → *Interpretación* (qué significa, en tono didáctico) → *Decisión que habilita* (pendiente, vinculada a SPEC/D-xx).
- Cierre: lista de PENDIENTES de SPEC que el perfilado informa (qué es falla, tolerancia R4, meta R6) sin resolverlos.
- Explicaciones en estilo académico (definir términos: perfilado, clave natural, mediana vs. media, etc.), como pidió el usuario.

## Archivos
- Crear `docs/perfilado.md` (entregable).
- Crear `docs/planes/03-perfilado.md` (copia de este plan, al aprobar).
- No se toca `drop/`, `SPEC.md`, `DECISIONES.md` ni `AI-LOG.md` (salvo registrar en `AI-LOG.md` un error de IA si ocurre durante el paso).
- Scripts temporales de consulta: scratchpad, fuera del repo.

## Verificación
1. Cada consulta del doc se re-ejecuta tal cual con `uv run python` + DuckDB y reproduce el resultado citado.
2. Cuadre: filas totales de `read_csv('drop/lecturas-*.csv', union_by_name=true)` = suma de filas por día = suma por equipo (≈115.000).
3. Contrastes con el dato: `ls drop/lecturas-*.csv | wc -l` = 30 coincide con H-01.
4. `git status --porcelain drop/` vacío y `git diff --exit-code 81956cb HEAD -- drop/` sin cambios (R2).
5. Cierre del paso: un commit (`docs: perfilado de drop/ (hallazgos H-01…)`) con `docs/perfilado.md` y `docs/planes/03-perfilado.md`.
