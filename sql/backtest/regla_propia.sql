-- Regla propia para el día D y una combinación (k, lecturas): alerta si vibración o temperatura
-- supera k veces el normal del equipo durante `n_min` lecturas seguidas (paso exacto de 15 min,
-- dentro del día D; un hueco corta la racha). Solo lee bt_normales del día y vista_lecturas.
INSERT INTO bt_alertas
WITH exceden AS (
    SELECT n.equipment_id, 'vib' AS variable, l.ts
    FROM bt_normales n
    JOIN vista_lecturas l ON l.equipment_id = n.equipment_id
     AND l.ts >= CAST(n.dia AS TIMESTAMP) AND l.ts < CAST(n.dia AS TIMESTAMP) + INTERVAL 1 DAY
    WHERE n.dia = getvariable('dia') AND l.vib_mm_s > getvariable('k') * n.normal_vib
    UNION ALL
    SELECT n.equipment_id, 'temp', l.ts
    FROM bt_normales n
    JOIN vista_lecturas l ON l.equipment_id = n.equipment_id
     AND l.ts >= CAST(n.dia AS TIMESTAMP) AND l.ts < CAST(n.dia AS TIMESTAMP) + INTERVAL 1 DAY
    WHERE n.dia = getvariable('dia') AND l.temp_c > getvariable('k') * n.normal_temp
),
rachas AS (
    SELECT equipment_id, variable, ts,
           CAST(epoch(ts) AS BIGINT) // 900
             - row_number() OVER (PARTITION BY equipment_id, variable ORDER BY ts) AS grupo
    FROM exceden
),
largas AS (
    SELECT equipment_id, variable, count(*) AS seguidas
    FROM rachas
    GROUP BY equipment_id, variable, grupo
    HAVING count(*) >= getvariable('n_min')
)
SELECT getvariable('combo_id'), getvariable('dia'), equipment_id,
       string_agg(DISTINCT variable, '+' ORDER BY variable), max(seguidas)
FROM largas
GROUP BY equipment_id;
