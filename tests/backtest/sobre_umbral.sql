-- Recalcula con una consulta independiente (directo sobre las lecturas completas, con ventana de rango
-- en vez de rachas) los días de alerta SU y los compara en ambos sentidos con bt_alertas.
WITH diario AS (
    SELECT l.equipment_id, CAST(l.ts AS DATE) AS dia,
           median(l.vib_mm_s) > any_value(e.umbral_vib_mm_s) AS sobre
    FROM limp.lecturas l JOIN limp.equipos e ON e.equipment_id = l.equipment_id
    GROUP BY l.equipment_id, CAST(l.ts AS DATE)
),
esperado AS (
    SELECT equipment_id, dia
    FROM (SELECT *, count_if(sobre) OVER (PARTITION BY equipment_id ORDER BY dia
                        RANGE BETWEEN to_days(getvariable('dias_seguidos') - 1) PRECEDING AND CURRENT ROW) AS n
          FROM diario)
    WHERE sobre AND n = getvariable('dias_seguidos')
      AND dia >= getvariable('primer_dia') AND dia <= CAST(getvariable('fin_datos') AS DATE) - 1
),
real AS (SELECT equipment_id, dia FROM bt_alertas WHERE combo_id = 'SU')
SELECT dia, equipment_id, 'alerta SU que el recálculo no ve' AS problema FROM (SELECT * FROM real EXCEPT SELECT * FROM esperado)
UNION ALL
SELECT dia, equipment_id, 'alerta SU que falta en el backtest' FROM (SELECT * FROM esperado EXCEPT SELECT * FROM real)
