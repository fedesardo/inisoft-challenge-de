-- Lista de cierre. Lee el resultado del backtest (bt_*) y las lecturas limpias. El "cierre" es la
-- última lectura de todo el drop (variable cierre). Variables: combo_id, cierre, dias_recientes,
-- horas_sin_lecturas.

-- Equipos sin lecturas en las últimas horas_sin_lecturas h antes del cierre (o sin ninguna): van aparte.
CREATE OR REPLACE TABLE sin_datos AS
SELECT e.equipment_id AS equipo, e.tipo, e.planta, max(l.ts) AS ultima_lectura,
       CAST(round(date_diff('minute', max(l.ts), CAST(getvariable('cierre') AS TIMESTAMP)) / 60.0) AS BIGINT) AS horas_sin_lecturas
FROM limp.equipos e
LEFT JOIN limp.lecturas l ON l.equipment_id = e.equipment_id
GROUP BY e.equipment_id, e.tipo, e.planta
HAVING max(l.ts) IS NULL
    OR max(l.ts) < CAST(getvariable('cierre') AS TIMESTAMP) - to_hours(getvariable('horas_sin_lecturas'));

-- Episodios activos: el último día de alerta cae en los últimos dias_recientes días de datos.
CREATE OR REPLACE TABLE lista_episodios AS
SELECT e.equipment_id AS equipo, e.primer_dia, e.ultimo_dia
FROM bt_episodios e
WHERE e.combo_id = getvariable('combo_id')
  AND e.ultimo_dia >= CAST(getvariable('cierre') AS DATE) - CAST(getvariable('dias_recientes') - 1 AS INTEGER)
  AND e.equipment_id NOT IN (SELECT equipo FROM sin_datos);

-- Una fila por episodio y señal alertada: desde qué día alertó esa señal, su normal ese día y su valor
-- reciente (mediana de las últimas 24 h antes del cierre). Comparar con el normal de cuando el equipo
-- empezó a desviarse (y no con el normal de hoy, que ya arrastra la subida) evita subestimar la desviación.
CREATE OR REPLACE TABLE lista_senales AS
WITH s AS (
    SELECT le.equipo, le.primer_dia, le.ultimo_dia, u.senal, min(a.dia) AS desde
    FROM lista_episodios le
    JOIN bt_alertas a ON a.combo_id = getvariable('combo_id') AND a.equipment_id = le.equipo
                     AND a.dia BETWEEN le.primer_dia AND le.ultimo_dia
    CROSS JOIN LATERAL (SELECT unnest(string_split(a.detalle, '+')) AS senal) u
    GROUP BY le.equipo, le.primer_dia, le.ultimo_dia, u.senal
),
actual AS (
    SELECT equipment_id, median(vib_mm_s) AS vib, median(temp_c) AS temp
    FROM limp.lecturas
    WHERE ts > CAST(getvariable('cierre') AS TIMESTAMP) - INTERVAL 24 HOUR
    GROUP BY equipment_id
)
SELECT s.equipo, s.senal, s.desde,
       CASE s.senal WHEN 'vib' THEN n.normal_vib ELSE n.normal_temp END AS normal,
       CASE s.senal WHEN 'vib' THEN a.vib ELSE a.temp END AS valor_actual
FROM s
JOIN bt_normales n ON n.equipment_id = s.equipo AND n.dia = s.desde
JOIN actual a ON a.equipment_id = s.equipo;

-- Sección aparte (D-31): episodios de la regla SU (mediana diaria de vibración sobre el umbral del
-- fabricante, dias_seguidos días seguidos) cuyo último día de alerta cae en los últimos dias_recientes
-- días de datos. Una racha de N días sobre el umbral da alertas desde su día N: la racha empieza
-- dias_seguidos - 1 días antes del primer día de alerta.
CREATE OR REPLACE TABLE su_episodios AS
WITH x AS (
    SELECT e.equipment_id AS equipo,
           e.primer_dia - CAST(getvariable('dias_seguidos') - 1 AS INTEGER) AS desde,
           e.ultimo_dia,
           e.dias_alerta + CAST(getvariable('dias_seguidos') - 1 AS INTEGER) AS dias_seguidos
    FROM bt_episodios e
    WHERE e.combo_id = 'SU'
      AND e.ultimo_dia >= CAST(getvariable('cierre') AS DATE) - CAST(getvariable('dias_recientes') - 1 AS INTEGER)
      AND e.equipment_id NOT IN (SELECT equipo FROM sin_datos)
)
SELECT x.equipo, x.desde, x.ultimo_dia, x.dias_seguidos,
       (SELECT median(l.vib_mm_s) FROM limp.lecturas l
         WHERE l.equipment_id = x.equipo AND CAST(l.ts AS DATE) = x.ultimo_dia) AS mediana_ultimo_dia,
       q.umbral_vib_mm_s AS umbral
FROM x JOIN limp.equipos q ON q.equipment_id = x.equipo;
