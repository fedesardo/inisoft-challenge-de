-- Episodios: días de alerta consecutivos del mismo equipo (misma regla) forman UN episodio.
-- Inicio = corte del primer día de alerta (día + 1 a las 00:00), cuando la alerta ya se conoce.
-- Clase (evaluación, mira el futuro a propósito; las reglas nunca lo vieron):
--   acierto_2_7: falla del mismo equipo entre 2 y 7 días después del inicio (métrica principal, D-08)
--   acierto_0_1: falla entre 0 y 2 días después (complementaria: no da tiempo de actuar)
--   falsa_alarma: sin falla en los 7 días siguientes
--   sin_evaluar: sin falla y los 7 días siguientes se pasan del último dato (D-19)
CREATE OR REPLACE TABLE bt_episodios AS
WITH g AS (
    SELECT combo_id, equipment_id, dia,
           dia - CAST(row_number() OVER (PARTITION BY combo_id, equipment_id ORDER BY dia) AS INTEGER) AS grupo
    FROM bt_alertas
),
e AS (
    SELECT combo_id, equipment_id, min(dia) AS primer_dia, max(dia) AS ultimo_dia, count(*) AS dias_alerta
    FROM g
    GROUP BY combo_id, equipment_id, grupo
),
con_falla AS (
    SELECT e.*,
           CAST(e.primer_dia + 1 AS TIMESTAMP) AS inicio,
           (SELECT min(o.fecha_apertura) FROM limp.ot o
             WHERE o.es_falla AND o.equipment_id = e.equipment_id
               AND o.fecha_apertura >= CAST(e.primer_dia + 1 AS TIMESTAMP)
               AND o.fecha_apertura <= CAST(e.primer_dia + 1 AS TIMESTAMP) + to_days(getvariable('horizonte'))) AS falla
    FROM e
)
SELECT combo_id, equipment_id, primer_dia, ultimo_dia, dias_alerta, inicio, falla,
       CAST(floor((epoch(falla) - epoch(inicio)) / 86400) AS INTEGER) AS anticipacion_dias,
       CASE WHEN falla IS NOT NULL
                 AND floor((epoch(falla) - epoch(inicio)) / 86400) >= getvariable('ant_min') THEN 'acierto_2_7'
            WHEN falla IS NOT NULL THEN 'acierto_0_1'
            WHEN inicio + to_days(getvariable('horizonte')) > CAST(getvariable('fin_datos') AS TIMESTAMP) THEN 'sin_evaluar'
            ELSE 'falsa_alarma' END AS clase
FROM con_falla;
