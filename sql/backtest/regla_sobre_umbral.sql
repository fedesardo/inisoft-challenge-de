-- Regla complementaria (id SU, D-31): alerta el día D si la mediana diaria de vibración de D y la de
-- los dias_seguidos - 1 días anteriores están todas sobre el umbral del fabricante (un día sin lecturas
-- corta la racha). Solo lee vista_lecturas y vista_equipos: nunca datos de D + 1 en adelante.
INSERT INTO bt_alertas
WITH diario AS (
    SELECT l.equipment_id, CAST(l.ts AS DATE) AS d, median(l.vib_mm_s) AS med, any_value(e.umbral_vib_mm_s) AS umbral
    FROM vista_lecturas l
    JOIN vista_equipos e ON e.equipment_id = l.equipment_id
    GROUP BY l.equipment_id, CAST(l.ts AS DATE)
),
sobre AS (
    SELECT equipment_id, d,
           d - CAST(row_number() OVER (PARTITION BY equipment_id ORDER BY d) AS INTEGER) AS grupo
    FROM diario
    WHERE med > umbral
),
rachas AS (
    SELECT equipment_id, count(*) AS dias, max(d) AS ultimo
    FROM sobre
    GROUP BY equipment_id, grupo
)
SELECT getvariable('combo_id'), getvariable('dia'), equipment_id, 'vib', dias
FROM rachas
WHERE ultimo = getvariable('dia') AND dias >= getvariable('dias_seguidos');
