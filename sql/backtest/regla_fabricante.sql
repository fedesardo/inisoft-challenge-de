-- Referencia ingenua (D-21): alerta el día D si alguna lectura de ese día supera el umbral del
-- fabricante (vibración o temperatura). Imita al sistema que apagaron: una sola lectura alcanza.
INSERT INTO bt_alertas
SELECT 'FAB', getvariable('dia'), l.equipment_id,
       CASE WHEN count_if(l.vib_mm_s > e.umbral_vib_mm_s) > 0
             AND count_if(l.temp_c > e.umbral_temp_c) > 0 THEN 'temp+vib'
            WHEN count_if(l.vib_mm_s > e.umbral_vib_mm_s) > 0 THEN 'vib'
            ELSE 'temp' END,
       count_if(l.vib_mm_s > e.umbral_vib_mm_s) + count_if(l.temp_c > e.umbral_temp_c)
FROM vista_lecturas l
JOIN vista_equipos e ON e.equipment_id = l.equipment_id
WHERE l.ts >= CAST(getvariable('dia') AS TIMESTAMP)
  AND l.ts < CAST(getvariable('dia') AS TIMESTAMP) + INTERVAL 1 DAY
GROUP BY l.equipment_id, e.umbral_vib_mm_s, e.umbral_temp_c
HAVING count_if(l.vib_mm_s > e.umbral_vib_mm_s) + count_if(l.temp_c > e.umbral_temp_c) > 0;
