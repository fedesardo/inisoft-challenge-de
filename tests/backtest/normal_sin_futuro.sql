-- Recalcula con una consulta independiente (directo sobre las lecturas y OT completas) el normal de
-- cada equipo y día, y devuelve las filas donde el backtest usó futuro, lecturas anteriores a la
-- última OT, o una mediana distinta.
WITH ref AS (
    SELECT n.dia, n.equipment_id, n.min_ts_usada, n.max_ts_usada, n.normal_vib, n.normal_temp,
           CAST(n.dia AS TIMESTAMP) AS d0,
           (SELECT max(o.fecha_apertura) FROM limp.ot o
             WHERE o.equipment_id = n.equipment_id
               AND o.fecha_apertura < CAST(n.dia AS TIMESTAMP) + INTERVAL 1 DAY) AS ultima_ot
    FROM bt_normales n
),
ini AS (
    SELECT *, greatest(d0 - to_days(getvariable('dias_ventana')), coalesce(ultima_ot, TIMESTAMP '1900-01-01')) AS inicio
    FROM ref
)
SELECT dia, equipment_id,
       CASE WHEN max_ts_usada >= d0 THEN 'usa lecturas del día evaluado o posteriores'
            WHEN min_ts_usada < inicio THEN 'usa lecturas anteriores a la última OT o a 7 días'
            WHEN abs(normal_vib - (SELECT median(l.vib_mm_s) FROM limp.lecturas l
                   WHERE l.equipment_id = ini.equipment_id AND l.ts >= ini.inicio AND l.ts < ini.d0)) > 1e-9
                 THEN 'mediana de vibración distinta de la recalculada'
            WHEN abs(normal_temp - (SELECT median(l.temp_c) FROM limp.lecturas l
                   WHERE l.equipment_id = ini.equipment_id AND l.ts >= ini.inicio AND l.ts < ini.d0)) > 1e-9
                 THEN 'mediana de temperatura distinta de la recalculada'
            WHEN inicio > d0 - to_days(getvariable('dias_minimos')) THEN 'evaluado con menos del mínimo de días'
       END AS problema
FROM ini
WHERE problema IS NOT NULL
