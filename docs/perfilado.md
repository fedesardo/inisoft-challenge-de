# Perfilado de `drop/` (paso 03)

- **Fecha:** 2026-11-16 · **Motor:** DuckDB 2.0.0 · **Fuente:** `drop/` en solo lectura (nada se modificó).
- **Qué es esto:** el *perfilado de datos* (data profiling) es la inspección sistemática de datos crudos —estructura, calidad, distribución— antes de transformarlos. Aquí **solo se observa**: las decisiones (qué es una falla, tolerancias, conversiones) se toman después, en `DECISIONES.md`, citando el número de hallazgo (H-NN).
- **Cómo reproducir:** cada hallazgo trae su consulta. Todas parten de las vistas de la sección "Preparación"; cada consulta se ejecutó tal cual contra `drop/`.

## Preparación: vistas comunes

Las lecturas se leen con `all_varchar=true`: todo como texto. Así DuckDB no adivina tipos y no puede esconder basura (por ejemplo un `"N/A"` en una columna numérica); después se castea con `TRY_CAST`, que devuelve NULL cuando no puede, y esos NULL se cuentan.
`union_by_name=true` une los CSV alineando por **nombre** de columna (no por posición); donde un formato no tiene la columna, queda NULL. `filename=true` agrega el archivo de origen.

```sql
CREATE VIEW raw AS SELECT * FROM read_csv('drop/lecturas-*.csv',
    union_by_name=true, filename=true, all_varchar=true);
CREATE VIEW eq  AS SELECT * FROM read_csv('drop/equipos.csv', all_varchar=true);
CREATE VIEW ot  AS SELECT * FROM read_csv('drop/ordenes-de-trabajo.csv', all_varchar=true);

-- l: los dos formatos con nombres unificados (viejo = tiene la columna equipment_id)
CREATE VIEW l AS SELECT filename, (equipment_id IS NOT NULL) viejo,
    coalesce(equipment_id, asset_id) eqid, coalesce(ts, timestamp) ts_txt,
    coalesce(vibracion_mm_s, vibration_mm_s) vib_txt,
    coalesce(temperatura_c, temp) temp_txt, unidad_temp
  FROM raw;

-- c: tipos reales, temperatura en °C (°F convertido), SIN el equipo de prueba (ver H-06)
CREATE VIEW c AS SELECT filename, viejo, eqid, CAST(ts_txt AS TIMESTAMP) ts,
    CAST(vib_txt AS DOUBLE) vib,
    CASE WHEN unidad_temp='F' THEN (CAST(temp_txt AS DOUBLE)-32)*5/9
         ELSE CAST(temp_txt AS DOUBLE) END temp_c,
    CAST(temp_txt AS DOUBLE) temp_raw, unidad_temp
  FROM l WHERE eqid <> 'EQ-TEST-01';
```

## Resumen de hallazgos

| Nº | Hallazgo | Magnitud | Por qué importa |
|---|---|---|---|
| H-01 | Dos formatos de lecturas; el cambio es el 11/02 | 10 archivos viejos + 20 nuevos; 115.065 filas | La ingesta debe unificar columnas |
| H-02 | Cada archivo trae su propio día; 40 equipos; filas por día | 3.863 viejo / 3.840 nuevo (fila "esperada") | Cuadre de filas (R4a) |
| H-03 | Duplicados solo en el sistema viejo, casi todos *conflictivos* | 229 claves duplicadas: 5 exactos, 224 con vibración distinta | "Descartar duplicados" exige elegir cuál fila queda |
| H-04 | Temperatura en °F en filas sueltas del sistema nuevo | 11.400 filas (14,9 % del nuevo), en los 40 equipos | Sin convertir, 14,9 % de lecturas "pasan" el umbral |
| H-05 | Sin nulos ni textos no numéricos; timestamps sin zona | 0 en ambos | Hallazgo negativo, también cuenta |
| H-06 | Equipo fantasma `EQ-TEST-01` | 48 filas, 2 días, 15 lecturas >100 °C | Debe excluirse; no está en el maestro |
| H-07 | Desfase horario de ~3 h entre sistemas | Pico diario de temperatura: ~14:30 (viejo) vs ~17:30 (nuevo) | Hipótesis UTC vs local, sin confirmar |
| H-08 | Huecos de lecturas | 220 lecturas faltantes; EQ-110 deja de reportar el 28/02 08:45 | EQ-110: ¿parado o sin datos? |
| H-09 | Cambio de nivel por equipo antes/después del 11/02 | 31 de 40 equipos estables (vib < 2 %, temp < 1 %); 9 con cambio | El cambio de sistema NO mueve el nivel (si se convierte °F) |
| H-10 | Sensores reemplazados (VX-200) leen casi cero | EQ-209 desde 14/02, EQ-118 desde 20/02: vib ≈ 0,08 | Señal "perfecta" que es sensor roto: riesgo de falso sano |
| H-11 | Maestro: umbrales por tipo, unidades coherentes | 3 tipos, 40 equipos, sin nulos | Umbral °C ↔ lecturas °C solo tras convertir °F |
| H-12 | Umbral contra lecturas: la alerta ingenua | 0,91 % vib y 14,92 % temp (sin convertir °F) en el nuevo | La "alarma que avisa todo el tiempo" nace de no convertir |
| H-13 | OT: IDs sucios pero todos cruzan al normalizar | 69/86 cruzan crudo; 86/86 normalizado | Normalizar ID es obligatorio y suficiente |
| H-14 | OT: tipos mezclados y 20 sin tipo | 61 preventivo, 5 correctivo, 20 vacíos | "Falla = tipo correctivo" no alcanza |
| H-15 | OT: fechas parsean y caen en el rango de lecturas | 01/02 09:45 a 02/03 16:45; 25 OT en los últimos 7 días | Las fallas del final no tienen ventana futura |
| H-16 | Fallas reales escondidas en el texto | 5 fallas con parada + 1 caso límite; 2 de las 5 sin tipo correctivo | Define el pendiente "qué cuenta como falla" |

---

## A. Lecturas: estructura

### H-01 · Dos formatos de archivo, cambio el 11/02
*Consulta:*
```sql
SELECT (equipment_id IS NOT NULL) AS viejo, count(DISTINCT filename) archivos, count(*) filas,
       min(regexp_extract(filename,'(\d{4}-\d\d-\d\d)',1)) desde,
       max(regexp_extract(filename,'(\d{4}-\d\d-\d\d)',1)) hasta
FROM raw GROUP BY 1;
```
*Resultado:* viejo: 10 archivos, 38.597 filas, 01/02–10/02. Nuevo: 20 archivos, 76.468 filas, 11/02–02/03. Total 115.065 filas en 30 archivos.
Encabezados: viejo `equipment_id, ts, vibracion_mm_s, temperatura_c`; nuevo `asset_id, timestamp, vibration_mm_s, temp, unidad_temp`.
*Interpretación:* el cliente tenía razón con la fecha. Cada formato nombra distinto las mismas 4 magnitudes; el nuevo agrega una columna de unidad. La unión por nombre deja `unidad_temp` en NULL para todo el sistema viejo (38.597 filas), que es la huella del cambio.
*Contraste:* `ls drop/lecturas-*.csv | wc -l` da 30.

### H-02 · Filas por día y por equipo
*Consulta:*
```sql
SELECT regexp_extract(filename,'(\d{4}-\d\d-\d\d)',1) dia, count(*) filas,
       count(DISTINCT eqid) equipos FROM l GROUP BY 1 ORDER BY 1;
```
*Resultado:* 40 equipos por día en casi todos; 41 el 20/02 y 21/02 (H-06); 39 el 01/03 y 02/03 (H-08). Filas por día: 3.863 en el viejo (3.840 = 40×96 más duplicados), 3.840 en el nuevo salvo días con huecos (3.744–3.864).
*Interpretación:* esperado = 40 equipos × 96 lecturas (cada 15 min) = 3.840/día. Las diferencias se explican con duplicados (H-03), equipo extra (H-06) y huecos (H-08).
Todo timestamp cae dentro del día de su archivo y en múltiplos exactos de 15 min:
```sql
SELECT (CAST(ts_txt AS TIMESTAMP)::date::varchar <> regexp_extract(filename,'(\d{4}-\d\d-\d\d)',1)) fuera_de_su_dia,
       viejo, count(*) FROM l GROUP BY 1,2;
SELECT viejo, sum((minute(CAST(ts_txt AS TIMESTAMP))%15<>0 OR second(CAST(ts_txt AS TIMESTAMP))<>0)::int) no_multiplo_15 FROM l GROUP BY 1;
```
→ 0 filas fuera de su día y 0 fuera de la grilla de 15 min, en ambos formatos.

## B. Calidad

### H-03 · Duplicados: solo el sistema viejo, y casi todos conflictivos
*Consulta:*
```sql
SELECT viejo, count(*) filas,
       count(*)-count(DISTINCT (eqid,ts_txt)) duplicados_clave,
       count(*)-count(DISTINCT (eqid,ts_txt,vib_txt,temp_txt)) duplicados_exactos
FROM l GROUP BY 1;

WITH d AS (SELECT eqid, ts_txt, count(*) c, count(DISTINCT vib_txt) dv, count(DISTINCT temp_txt) dt
           FROM l WHERE viejo GROUP BY 1,2 HAVING count(*)>1)
SELECT c filas_por_clave, count(*) claves, sum((dv>1)::int) vib_distinta, sum((dt>1)::int) temp_distinta FROM d GROUP BY 1;
```
*Resultado:* viejo: 229 claves (equipo, timestamp) repetidas, todas exactamente 2 filas; **solo 5 son idénticas**; en 224 cambia la vibración y la temperatura es siempre igual. Nuevo: 0. Ejemplo: EQ-104, 2026-02-06 03:00:00 → vib 3,192 y 3,181, temp 55,51 en ambas.
*Interpretación:* la *clave natural* es (equipo, timestamp). Un duplicado **exacto** es un reenvío puro; uno **conflictivo** comparte clave pero no valores. El cliente decía "la misma lectura más de una vez": no es del todo cierto, la reenvía con una vibración levemente distinta (diferencias de ~0,01). Hay que elegir una regla (primera, última o promedio) y registrarla. Confirma la asunción de SPEC: duplicados solo en el viejo.
*Habilita:* regla de deduplicación en R4 (pendiente).

### H-05 · Nulos, textos no numéricos y zona horaria declarada
*Consulta:*
```sql
SELECT viejo, count(*) n, count(*)-count(eqid) n_eq, count(*)-count(ts_txt) n_ts,
       count(*)-count(vib_txt) n_vib, count(*)-count(temp_txt) n_temp FROM l GROUP BY 1;
SELECT viejo, sum((TRY_CAST(vib_txt AS DOUBLE) IS NULL AND vib_txt IS NOT NULL)::int) vib_no_num,
       sum((TRY_CAST(temp_txt AS DOUBLE) IS NULL AND temp_txt IS NOT NULL)::int) temp_no_num,
       sum((TRY_CAST(ts_txt AS TIMESTAMP) IS NULL)::int) ts_no_parsea FROM l GROUP BY 1;
SELECT viejo, length(ts_txt) largo, count(*) FROM l GROUP BY 1,2;
```
*Resultado:* 0 nulos, 0 textos no numéricos, 0 timestamps que no parsean. Todos tienen 19 caracteres (`YYYY-MM-DD HH:MM:SS` viejo; `YYYY-MM-DDTHH:MM:SS` nuevo): **ninguno trae sufijo `Z` ni offset**, o sea la zona horaria no está declarada.
*Interpretación:* un hallazgo negativo también es evidencia. El formato de texto difiere solo en la `T`, que DuckDB entiende. Que no haya zona declarada es justo lo que vuelve relevante H-07.

### H-06 · Equipo fantasma `EQ-TEST-01`
*Consulta:*
```sql
SELECT eqid, count(*) n FROM l WHERE eqid NOT IN (SELECT equipment_id FROM eq) GROUP BY 1;
SELECT eqid, min(ts_txt) desde, max(ts_txt) hasta, count(*) n FROM l WHERE eqid='EQ-TEST-01' GROUP BY 1;
SELECT count(*) filas_C_sobre_100, count(DISTINCT eqid) FROM l WHERE unidad_temp='C' AND TRY_CAST(temp_txt AS DOUBLE)>100;
```
*Resultado:* único ID de lecturas que no está en el maestro: `EQ-TEST-01`, 48 filas (una por hora, 20/02 00:00 a 21/02 23:00), solo en formato nuevo. Es el único equipo con "°C" mayores a 100 (15 filas, todas suyas).
*Interpretación:* parece una prueba de instalación del sistema nuevo. No pertenece al universo de 40 equipos; se excluye de la vista `c`. Explica el 41 de H-02.

## C. Unidades, rangos y zona horaria

### H-04 · °F mezclados con °C en el sistema nuevo
*Consulta:*
```sql
SELECT unidad_temp, count(DISTINCT eqid) equipos, count(*) filas FROM l WHERE unidad_temp IS NOT NULL GROUP BY 1;

SELECT viejo, unidad_temp, count(*) n,
  round(min(TRY_CAST(temp_txt AS DOUBLE)),1) tmin, round(median(TRY_CAST(temp_txt AS DOUBLE)),1) tmed,
  round(max(TRY_CAST(temp_txt AS DOUBLE)),1) tmax,
  round(min(TRY_CAST(vib_txt AS DOUBLE)),2) vmin, round(median(TRY_CAST(vib_txt AS DOUBLE)),2) vmed,
  round(max(TRY_CAST(vib_txt AS DOUBLE)),2) vmax
FROM l GROUP BY 1,2 ORDER BY 1,2;

SELECT count(*) FROM l WHERE unidad_temp='F' AND (TRY_CAST(temp_txt AS DOUBLE)-32)*5/9 > 100;
```
*Resultado:* `unidad_temp`: C = 65.068 filas, F = 11.400, vacío = 38.597 (el sistema viejo). Las filas °F **no son equipos enteros**: están repartidas en los 40 equipos (~16 % de cada uno, p. ej. EQ-104 17,1 %). Rangos: viejo 52,6–79,4 °C (mediana 64,6); nuevo en C mediana 65,9; nuevo en F mediana 149,3, mín. 126,7, máx. 204,4. Convertidas con (F−32)·5/9, ninguna pasa de 100 °C.
*Interpretación:* 149,3 °F ≈ 65,2 °C: casi idéntico a la mediana del viejo (64,6 °C), lo que confirma que son °F reales y no un error. La fórmula °C = (°F − 32) × 5/9 se aplica fila a fila según `unidad_temp`. El viejo se asume en °C (rango 52–79 coherente) pero **no lo declara**.
*Habilita:* regla de conversión (decisión pendiente).

### H-07 · Desfase horario de ~3 h entre sistemas (hipótesis)
*Consulta:*
```sql
SELECT hour(ts) h, round(avg(temp_c) FILTER (WHERE viejo),1) viejo_temp,
       round(avg(temp_c) FILTER (WHERE NOT viejo),1) nuevo_temp,
       round(avg(vib) FILTER (WHERE viejo),2) viejo_vib, round(avg(vib) FILTER (WHERE NOT viejo),2) nuevo_vib
FROM c GROUP BY 1 ORDER BY 1;
```
*Resultado:* la temperatura sigue un ciclo diario. Sistema viejo: máximo 68,2 °C a las 14–15 h y mínimo 62,2 a las 02 h. Sistema nuevo: máximo 68,5 a las 17–18 h y mínimo 62,6 a las 05–06 h. Corrimiento: **+3 horas**. La vibración no tiene ciclo (2,58 vs 2,56 plano).
*Interpretación:* si la temperatura sigue el ritmo del día real (más calor por la tarde), que el pico se mueva 3 h delata que los timestamps no están en la misma zona. Una explicación posible es que el sistema nuevo guarde UTC y el viejo la hora local (UTC−3), pero **es una inferencia, no un dato**: el cliente no documentó el cambio. Se debe confirmar con el cliente (Mauro o Julián) o asumir y escribir la asunción.
*Impacto:* para métricas diarias casi no cambia nada; sí importa para "última lectura", cortes diarios y ventanas de 2–7 días. Habilita decisión de zona horaria.

### H-08 · Huecos de lecturas
*Consulta:*
```sql
SELECT count(*) equipo_dias, sum((n<96)::int) con_huecos, min(n) min_n, sum(96-n) lecturas_faltantes
FROM (SELECT eqid, ts::date d, count(DISTINCT ts) n FROM c GROUP BY 1,2);

SELECT eqid, count(DISTINCT ts) n, min(ts) desde, max(ts) hasta, 2880-count(DISTINCT ts) faltan
FROM c GROUP BY 1 HAVING count(DISTINCT ts)<>2880 ORDER BY n;

WITH g AS (SELECT eqid, ts, ts-lag(ts) OVER (PARTITION BY eqid ORDER BY ts) gap
           FROM (SELECT DISTINCT eqid, ts FROM c))
SELECT eqid, ts-gap antes, ts hasta, gap FROM g WHERE gap>INTERVAL 15 MINUTE ORDER BY gap DESC LIMIT 15;
```
*Resultado:* 1.198 combinaciones equipo-día; 7 con huecos; 220 lecturas faltantes (2880 = 30 días × 96). Dos patrones:
1. **EQ-110**: 2.628 de 2.880; su último dato es 28/02 08:45 (faltan 252): deja de reportar y no vuelve.
2. **Cinco equipos** (EQ-107, EQ-112, EQ-116, EQ-209, EQ-214) con un único hueco de 8 h 15 min cada uno (32 lecturas): EQ-107 el 09/02, EQ-214 el 16/02, EQ-116 el 19/02, EQ-112 el 22/02, EQ-209 el 27/02. Las fechas coinciden con OT correctivas de esos equipos (H-16).
*Interpretación:* un hueco no es una lectura normal ni "cero": es ausencia de dato, y hay que tratarla distinto (no imputar). Que los huecos coincidan con fallas sugiere que el equipo estaba parado: **la ausencia de datos es información**. Que EQ-110 se calle desde el 28/02 y no tenga OT que lo explique (H-16) es un caso a vigilar.

## D. Cambio de sistema por equipo

### H-09 · Nivel antes y después del 11/02
*Consulta:*
```sql
WITH x AS (SELECT eqid,
   round(median(temp_c) FILTER (WHERE viejo),2) t_antes, round(median(temp_c) FILTER (WHERE NOT viejo),2) t_desp,
   round(median(temp_raw) FILTER (WHERE NOT viejo),2) t_desp_sin_convertir,
   round(median(vib) FILTER (WHERE viejo),3) v_antes, round(median(vib) FILTER (WHERE NOT viejo),3) v_desp
 FROM c GROUP BY 1)
SELECT *, round(t_desp-t_antes,2) dT, round(100*(t_desp/t_antes-1),1) pctT, round(100*(v_desp/v_antes-1),1) pctV
FROM x ORDER BY abs(v_desp/v_antes-1) DESC;
```
*Resultado (resumen, mediana por equipo):* con °F convertido, la mediana del cambio de temperatura entre equipos es −0,01 %; el rango va de −0,33 % a +9,8 %. Sin convertir, la mediana del nuevo sube ~0,8 °C en todos los equipos (columna `t_desp_sin_convertir`), efecto puramente de unidad.
- **31 de 40 equipos** son estables: cambian como máximo 1,61 % en vibración y 0,33 % en temperatura (ejemplos: EQ-101 −0,1 % / −0,1 %; EQ-217 0,0 % / 0,0 %).
- **9 equipos cambian** (|vib| ≥ 2 % o |temp| ≥ 1 %): EQ-107, EQ-115, EQ-118, EQ-203, EQ-206, EQ-209 (vibración) y EQ-102, EQ-214, EQ-219 (temperatura). Los cinco más marcados:

| Equipo | Qué cambia | Magnitud |
|---|---|---|
| EQ-209 | Vibración cae | 2,054 → 0,085 (−95,9 %) |
| EQ-118 | Vibración cae | 2,145 → 0,222 (−89,7 %) |
| EQ-115 | Vibración sube | 3,243 → 4,977 (+53,5 %) |
| EQ-102 | Temperatura sube | 58,41 → 64,13 °C (+9,8 %) |
| EQ-219 | Temperatura sube | 59,73 → 61,99 °C (+3,8 %) |

Los otros cuatro: EQ-107 (vib −19,2 %), EQ-203 (+18,2 %), EQ-206 (−5,1 %) y EQ-214 (temp +1,5 %). El umbral de 2 % / 1 % usado para separar "estable" de "cambia" es solo descriptivo de este perfilado, no una decisión de tolerancia.

*Interpretación (la pregunta del plan):* si el cambio de sistema fuera el culpable, **los 40 equipos se moverían juntos el 11/02**. No pasa: la mediana de todos es ~0. Entonces, una vez convertido °F (H-04), el sistema nuevo mide el mismo nivel que el viejo. Los 9 equipos con cambio se mueven de a uno y a su propio ritmo (ver H-10 y H-16), es decir, son eventos propios de esos equipos y no del sistema. Se usa **mediana** porque no la arrastran los picos como sí lo hace la media: hay 16 lecturas de vibración mayores a 10 mm/s (máximo 32,8) repartidas de a 1 o 2 en 12 equipos, picos aislados (`SELECT eqid, count(*) FROM c WHERE vib>10 GROUP BY 1`).
Trayectorias diarias de esos equipos (consulta de apoyo):
```sql
SELECT ts::date d, round(avg(vib) FILTER (WHERE eqid='EQ-209'),2) v209, round(avg(vib) FILTER (WHERE eqid='EQ-118'),2) v118,
  round(avg(vib) FILTER (WHERE eqid='EQ-115'),2) v115, round(avg(temp_c) FILTER (WHERE eqid='EQ-102'),1) t102,
  round(avg(temp_c) FILTER (WHERE eqid='EQ-219'),1) t219 FROM c GROUP BY 1 ORDER BY 1;
```
- **EQ-115** sube en vibración de forma sostenida desde ~3,2 (01/02) hasta 9,34 (02/03), muy por encima de su umbral (es una bomba: 7,1). Degradación gradual.
- **EQ-102** sube su temperatura desde el 16/02 (58,4 → 75,5 °C el 02/03), crecimiento casi lineal.
- **EQ-219** sube de 59,7 a 65,9 °C desde el 21/02 y **queda clavado en 65,9 desde el 25/02** (valor idéntico seis días seguidos: sospechoso de sensor trabado).
*Habilita:* tolerancia de R4(c): entre los 31 equipos estables el cambio máximo es 1,61 % (vib) y 0,33 % (temp); la tolerancia debe quedar por encima de eso y por debajo de los saltos reales (pendiente de decidir).

### H-10 · Sensores de vibración reemplazados: leen casi cero
*Consulta:* las de H-09 (columnas v209 y v118) y las OT de H-16.
*Resultado:* EQ-209: vibración ~2,05 hasta el 13/02; 1,23 el 14/02; **0,08 desde el 15/02**. Hay una OT del 14/02 11:00: *"Reemplazo de sensor de vibración por fin de vida útil. Se instala VX-200 (proveedor nuevo), configuración de fábrica"*. EQ-118: ~2,15 hasta el 19/02; 1,66 el 20/02; **0,08 desde el 21/02**; OT del 20/02 15:00: *"cambio sensor vibr. -> VX-200. queda andando"* (sin tipo). Luego la vibración de ambos se mueve apenas (0,08–0,21).
*Interpretación:* la caída coincide al día con la OT del cambio de sensor. Nadie se curó el 90 %: el sensor nuevo (VX-200, "configuración de fábrica") mide en otra escala o está mal calibrado. Esto es una trampa: una señal en 0,08 *parece* un equipo sanísimo, pero está **ciego**. La OT 40283 (EQ-209, 27/02) lo confirma: *"Equipo parado por operador: ruido fuerte y vibración. Rodam. dañado, se cambia. Llama la atención que el monitoreo no mostró nada raro."* El equipo falló con el monitoreo en 0,08.
*Impacto:* cualquier criterio basado en vibración absoluta o en "lectura baja = sano" dejaría pasar justo la falla. Hay que detectar "sensor sospechosamente quieto o muerto" como una señal en sí misma.

## E. Maestro de equipos

### H-11 · Estructura y unidades del maestro
*Consulta:*
```sql
SELECT count(*) filas, count(DISTINCT equipment_id) ids, string_agg(DISTINCT tipo, ',') tipos,
       string_agg(DISTINCT planta, ',') plantas, sum((umbral_vib_mm_s IS NULL OR umbral_temp_c IS NULL)::int) nulos FROM eq;

SELECT tipo, count(*) n, min(CAST(umbral_vib_mm_s AS DOUBLE)) vib_min, max(CAST(umbral_vib_mm_s AS DOUBLE)) vib_max,
       min(CAST(umbral_temp_c AS DOUBLE)) t_min, max(CAST(umbral_temp_c AS DOUBLE)) t_max FROM eq GROUP BY 1;
```
*Resultado:* 40 filas, 40 IDs únicos, sin nulos; tipos bomba/compresor/turbina; plantas norte/sur. **Un único umbral por tipo**:

| Tipo | Equipos | Umbral vib (mm/s) | Umbral temp (°C) |
|---|---|---|---|
| bomba | 20 | 7,1 | 85 |
| compresor | 13 | 4,5 | 95 |
| turbina | 7 | 2,8 | 110 |

*Interpretación:* las columnas dicen `_mm_s` y `_c`: **las unidades coinciden** con las de lectura (mm/s y °C), siempre que las lecturas °F se conviertan antes de comparar. Pero el umbral es de fabricante por tipo: no refleja el nivel normal de cada equipo individual. Ejemplo: EQ-206 y EQ-112 (turbinas) tienen umbral de vibración 2,8, mientras que una bomba como EQ-115 tiene 7,1: el mismo valor de vibración significa cosas distintas según el tipo.

### H-12 · Umbral contra lecturas: de dónde sale la alerta que "avisa todo el tiempo"
*Consulta:*
```sql
WITH p AS (SELECT c.viejo, c.vib>CAST(e.umbral_vib_mm_s AS DOUBLE) sv,
                  c.temp_c>CAST(e.umbral_temp_c AS DOUBLE) st, c.temp_raw>CAST(e.umbral_temp_c AS DOUBLE) st_crudo
           FROM c JOIN eq e ON e.equipment_id=c.eqid)
SELECT viejo, count(*) n, round(100*avg(sv::int),2) pct_vib_sobre_umbral,
       round(100*avg(st::int),3) pct_temp_sobre_umbral, round(100*avg(st_crudo::int),2) pct_temp_sobre_umbral_sin_convertir
FROM p GROUP BY 1;

SELECT eqid, count(*) filas_vib_sobre_umbral FROM c JOIN eq e ON e.equipment_id=c.eqid
WHERE vib>CAST(e.umbral_vib_mm_s AS DOUBLE) GROUP BY 1 ORDER BY 2 DESC LIMIT 12;
```
*Resultado:* sistema viejo: 0,24 % de lecturas de vibración sobre umbral y 0 % de temperatura. Sistema nuevo: 0,91 % de vibración y 0,004 % de temperatura convertida, **pero 14,92 % de temperatura si no se convierte °F** (por eso 149 "°C" superan 85–110). Las lecturas sobre umbral de vibración se concentran en pocos equipos: EQ-115 (450), EQ-206 (116), EQ-107 (78), EQ-112 (77), EQ-203 (34); los demás tienen 3 o menos.
*Interpretación:* esto es el mecanismo del problema que contó el cliente. Una alerta ingenua por umbral que no convierta °F dispararía en 1 de cada 7 lecturas del sistema nuevo. Con la conversión, la alerta por umbral es mucho más callada, y los equipos que la disparan son los de verdad degradados. Sirve de **referencia ingenua** para el backtest (R6).

## F. Órdenes de trabajo

### H-13 · IDs de equipo en OT
*Consulta:*
```sql
SELECT count(*) ot_total,
  sum((equipo IN (SELECT equipment_id FROM eq))::int) cruzan_crudo,
  sum((upper(regexp_replace(trim(equipo),'^(?i)eq-?','EQ-')) IN (SELECT equipment_id FROM eq))::int) cruzan_normalizado
FROM ot;
SELECT equipo, count(*) FROM ot WHERE equipo NOT SIMILAR TO 'EQ-[0-9]+' GROUP BY 1 ORDER BY 1;
```
*Resultado:* 86 OT, 86 `nro_ot` únicos. Con el ID tal cual, 69 cruzan con el maestro; **17 no** (`EQ103`, `eq-117`, `EQ-101` con espacio al principio, etc.). Normalizando (recortar espacios, mayúsculas, insertar guion) cruzan **86 de 86**; ningún ID queda huérfano.
*Interpretación:* los IDs son sucios pero recuperables y la regla de normalización es suficiente. Si no se normalizaran, se perderían 17 OT (el 20 %) y las fallas de esos equipos desaparecerían en silencio.

### H-14 · Tipos de OT
*Consulta:*
```sql
SELECT coalesce(tipo,'<vacío>') tipo, count(*) n FROM ot GROUP BY 1 ORDER BY 2 DESC;
```
*Resultado:* `PREV` 42, `<vacío>` 20, `Preventivo` 19, `Correctivo` 4, `CORR` 1. Son 5 valores para 3 conceptos: preventivo = 61, correctivo = 5, sin tipo = 20.
*Interpretación:* `PREV`/`Preventivo` y `CORR`/`Correctivo` son sinónimos. Solo 5 OT dicen "correctivo", y el cliente avisó que "no siempre ponen el tipo": 20 (23 %) no lo tienen.

### H-15 · Fechas de OT contra el rango de lecturas
*Consulta:*
```sql
SELECT sum((TRY_STRPTIME(fecha_apertura,'%d/%m/%Y %H:%M') IS NULL)::int) apertura_no_parsea,
  sum((fecha_cierre IS NULL OR fecha_cierre='')::int) cierre_vacio,
  sum((TRY_STRPTIME(fecha_cierre,'%d/%m/%Y %H:%M') < TRY_STRPTIME(fecha_apertura,'%d/%m/%Y %H:%M'))::int) cierre_antes_apertura,
  min(TRY_STRPTIME(fecha_apertura,'%d/%m/%Y %H:%M')) min_ap, max(TRY_STRPTIME(fecha_apertura,'%d/%m/%Y %H:%M')) max_ap
FROM ot;
SELECT count(*) ot_ultimos_7d FROM ot WHERE TRY_STRPTIME(fecha_apertura,'%d/%m/%Y %H:%M') >= TIMESTAMP '2026-02-23 23:45:00';
```
*Resultado:* todas las fechas parsean con `dd/mm/yyyy hh:mm`; ningún cierre vacío ni anterior a la apertura. Aperturas del 01/02 09:45 al 02/03 16:45, dentro del rango de lecturas (01/02 00:00 a 02/03 23:45). 25 de las 86 OT caen en los últimos 7 días.
*Interpretación:* las OT y las lecturas cubren el mismo mes, así que se pueden cruzar. Pero el backtest evalúa "falla entre 2 y 7 días después del corte" (R6): las fallas de los últimos días del mes no tienen 7 días de futuro observable, y hay que excluir esos cortes o declararlo. Además las OT están en hora local sin zona declarada: mismo problema de H-07 al compararlas con las lecturas.

### H-16 · Fallas reales y su descripción
*Consulta:*
```sql
SELECT nro_ot, upper(regexp_replace(trim(equipo),'^(?i)eq-?','EQ-')) eq_norm,
       TRY_STRPTIME(fecha_apertura,'%d/%m/%Y %H:%M') apertura, coalesce(tipo,'<vacío>') tipo, left(descripcion,70) descr
FROM ot
WHERE tipo IN ('CORR','Correctivo')
   OR tipo IS NULL AND descripcion NOT SIMILAR TO '(Verificación|Lubricación|Limpieza|Ajuste|insp|Inspección|Control|Cambio de aceite).*'
   OR descripcion ILIKE '%sensor%' OR descripcion ILIKE '%rodamiento%'
ORDER BY apertura;
```
*Resultado (OT que describen una avería o un hecho no rutinario):*

| OT | Equipo | Apertura | Tipo | Qué dice la descripción | ¿Falla? |
|---|---|---|---|---|---|
| 40227 | EQ-107 | 09/02 10:00 | Correctivo | Parada no programada, rotura de rodamiento; operador oyó ruido días antes | Sí |
| 40246 | EQ-206 | 15/02 10:00 | Correctivo | Vibración alta en ronda, alineación y balanceo; equipo sigue en servicio | Intervención sin parada |
| 40252 | EQ-214 | 16/02 14:00 | **vacío** | Disparo por alta temperatura, intercambiador obstruido, equipo detenido ~8 h | Sí |
| 40255 | EQ-120 | 18/02 14:00 | Correctivo | Reclamo por ruido; se inspecciona, sin hallazgos | **No** (tipo correctivo, no hay falla) |
| 40256 | EQ-116 | 19/02 03:00 | Correctivo | Pérdida de sello mecánico, parada de urgencia; sin aviso previo | Sí |
| 40269 | EQ-112 | 22/02 08:00 | CORR | Turbina sale de servicio por vibración muy alta (actúa protección); desbalanceo | Sí |
| 40283 | EQ-209 | 27/02 09:00 | **vacío** | Equipo parado por operador, rodamiento dañado; el monitoreo no mostró nada | Sí |
| 40254 | EQ-115 | 18/02 11:00 | PREV | Ruido en rodamiento LOA, persiste; recomienda cambio en próxima parada | Aviso, no falla (aún) |

También hay OT no-falla que parecen rutina con contenido relevante: 40244 (EQ-209, 14/02, cambio de sensor, tipo "Preventivo") y 40264 (EQ-118, 20/02, cambio de sensor, sin tipo), ver H-10; 40250 (EQ-101, revisión de cableado, sin falla) y 40277 (EQ-205, pedido de repuesto, sin falla).
*Interpretación:* contar solo `tipo = correctivo` daría 5 OT (EQ-107, 206, 120, 116, 112), pero **el campo tipo falla en los dos sentidos**: EQ-120 es "correctivo" sin falla (falso positivo) y EQ-206 es una intervención sin parada (caso límite); en cambio EQ-214 y EQ-209 son fallas reales con el tipo vacío (falsos negativos). Resultado: la regla "falla = correctivo" **dejaría fuera 2 de las 5 fallas con parada** (EQ-107, 214, 116, 112, 209) y sumaría 1 que no lo es. La señal está en la descripción (parada, rotura, disparo, fuera de servicio), no en el campo tipo. Con ~5 fallas el backtest es evidencia modesta (D-05).
Los cinco equipos con hueco de 8 h de lecturas (H-08) son justamente los de las fallas con parada: EQ-107, 214, 116, 112 y 209, y el hueco cae el mismo día de su OT. Eso sugiere equipo parado. EQ-116 además es una falla "sin aviso previo" según su OT: si no hubo señal anticipable, no hay nada que detectar, lo que pone en duda la asunción D-07 para esa falla.
*Habilita:* regla de falla (PENDIENTE de R3), y el plan de la ventana P-F (R7).

---

## Qué informa el perfilado sobre los PENDIENTES de SPEC (sin resolverlos)

1. **¿Qué cuenta como falla? (R3):** el campo `tipo` no alcanza (H-14, H-16). Hay que decidir si se interpreta la descripción y cómo.
2. **Tolerancia de R4(c):** con °F convertido, 31 de 40 equipos cambian como máximo 1,61 % (vib) y 0,33 % (temp) entre sistemas (H-09). La tolerancia debe quedar por encima de ese ruido y por debajo de los saltos reales (9 equipos).
3. **Regla de duplicados (R4):** hay que elegir entre las dos filas de 224 pares conflictivos (H-03).
4. **Zona horaria:** hay un desfase de ~3 h sin documentar (H-07). Confirmar con el cliente o asumir por escrito.
5. **Sensores muertos (H-10):** hacen falta una señal de "sensor sospechosamente quieto" y una decisión sobre cómo tratar EQ-209 y EQ-118.
6. **Meta de R6:** con ~5 fallas, cada acierto o error mueve mucho el porcentaje: la meta numérica debe expresarse en conteos, no solo en % (D-05).

## Preguntas abiertas para el cliente
- ¿El sistema nuevo guarda UTC o hora local? (H-07)
- ¿`EQ-TEST-01` es un equipo de prueba? (H-06)
- ¿El sensor VX-200 se calibró? ¿Qué escala usa? (H-10)
- ¿EQ-110 está fuera de servicio desde el 28/02? (H-08)
- ¿"Correctivo" incluye inspecciones sin hallazgos (OT 40255)? (H-16)

## Cuadre de cifras
- Filas crudas: 115.065 = 38.597 (viejo) + 76.468 (nuevo) ✓ (H-01).
- Filas limpias (insumo de R4a): 115.065 − 229 duplicados − 48 de `EQ-TEST-01` = **114.788**.
