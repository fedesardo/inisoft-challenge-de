-- Por falla y por regla: ¿tuvo un episodio que empezó entre 0 y 7 días antes? La anticipación es
-- la del PRIMER episodio (el más temprano) dentro de esa ventana. Las fallas anteriores al primer
-- día evaluado quedan aparte ('fuera_de_evaluacion').
CREATE OR REPLACE TABLE bt_fallas AS
WITH f AS (
    SELECT nro_ot, equipment_id, fecha_apertura AS fecha_falla FROM limp.ot WHERE es_falla
),
x AS (
    SELECT c.orden, c.combo_id, f.equipment_id, f.nro_ot, f.fecha_falla,
           (SELECT min(e.inicio) FROM bt_episodios e
             WHERE e.combo_id = c.combo_id AND e.equipment_id = f.equipment_id
               AND e.inicio <= f.fecha_falla
               AND e.inicio >= f.fecha_falla - to_days(getvariable('horizonte'))) AS inicio_episodio
    FROM f CROSS JOIN bt_combos c
)
SELECT orden, combo_id, equipment_id, nro_ot, fecha_falla, inicio_episodio,
       CAST(floor((epoch(fecha_falla) - epoch(inicio_episodio)) / 86400) AS INTEGER) AS anticipacion_dias,
       CASE WHEN fecha_falla < CAST(getvariable('primer_dia') AS TIMESTAMP) THEN 'fuera_de_evaluacion'
            WHEN inicio_episodio IS NULL THEN 'sin_aviso'
            WHEN floor((epoch(fecha_falla) - epoch(inicio_episodio)) / 86400) >= getvariable('ant_min')
                 THEN 'anticipada_2d'
            ELSE 'avisada_menos_2d' END AS clase
FROM x;

-- Días en los que un episodio recién iniciado ya tiene sus 7 días siguientes completos:
-- de primer_dia a (fin_datos - 8 días). Es el denominador de "falsas alarmas por semana".
CREATE OR REPLACE TABLE bt_resumen AS
WITH dias AS (
    SELECT date_diff('day', getvariable('primer_dia'),
                     CAST(getvariable('fin_datos') AS DATE) - to_days(getvariable('horizonte') + 1)) + 1 AS n
)
SELECT c.orden, c.combo_id, c.regla, c.k, c.lecturas_seguidas,
       (SELECT count(*) FROM bt_fallas f WHERE f.combo_id = c.combo_id AND f.clase <> 'fuera_de_evaluacion') AS fallas_evaluables,
       (SELECT count(*) FROM bt_fallas f WHERE f.combo_id = c.combo_id AND f.clase = 'anticipada_2d') AS fallas_anticipadas_2d,
       (SELECT count(*) FROM bt_fallas f WHERE f.combo_id = c.combo_id AND f.clase IN ('anticipada_2d', 'avisada_menos_2d')) AS fallas_con_episodio_7d,
       (SELECT median(anticipacion_dias) FROM bt_fallas f WHERE f.combo_id = c.combo_id AND f.clase = 'anticipada_2d') AS anticipacion_mediana_dias_2d,
       (SELECT median(anticipacion_dias) FROM bt_fallas f WHERE f.combo_id = c.combo_id AND f.clase IN ('anticipada_2d', 'avisada_menos_2d')) AS anticipacion_mediana_dias_7d,
       (SELECT count(*) FROM bt_episodios e WHERE e.combo_id = c.combo_id) AS episodios,
       (SELECT count(DISTINCT equipment_id) FROM bt_episodios e WHERE e.combo_id = c.combo_id) AS equipos_marcados,
       (SELECT count(*) FROM bt_episodios e WHERE e.combo_id = c.combo_id AND e.clase = 'falsa_alarma') AS falsas_alarmas,
       (SELECT count(*) FROM bt_episodios e WHERE e.combo_id = c.combo_id AND e.clase = 'sin_evaluar') AS episodios_sin_evaluar,
       (SELECT n FROM dias) AS dias_para_falsas_alarmas,
       CASE WHEN (SELECT n FROM dias) > 0 THEN
       round((SELECT count(*) FROM bt_episodios e WHERE e.combo_id = c.combo_id AND e.clase = 'falsa_alarma')
             / ((SELECT n FROM dias) / 7.0), 2) END AS falsas_alarmas_por_semana
FROM bt_combos c;
