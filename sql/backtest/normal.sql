-- El normal de cada equipo para el día evaluado D: mediana de vibración y de temperatura de las
-- lecturas en [inicio_ventana, D), donde inicio_ventana = el más tardío entre (D - 7 días) y la
-- última OT conocida (D-26: toda OT reinicia el normal). Nunca usa lecturas de D en adelante.
-- Si entre inicio_ventana y D no hay al menos 1 día, el equipo no se evalúa ese día.
INSERT INTO bt_normales
WITH ventana AS (
    SELECT e.equipment_id,
           greatest(CAST(getvariable('dia') AS TIMESTAMP) - to_days(getvariable('dias_ventana')),
                    coalesce(max(o.fecha_apertura), TIMESTAMP '1900-01-01')) AS inicio_ventana
    FROM vista_equipos e
    LEFT JOIN vista_ot o ON o.equipment_id = e.equipment_id
    GROUP BY e.equipment_id
)
SELECT getvariable('dia'), v.equipment_id, v.inicio_ventana,
       min(l.ts), max(l.ts), count(*),
       median(l.vib_mm_s), median(l.temp_c)
FROM ventana v
JOIN vista_lecturas l
  ON l.equipment_id = v.equipment_id
 AND l.ts >= v.inicio_ventana
 AND l.ts < CAST(getvariable('dia') AS TIMESTAMP)
WHERE v.inicio_ventana <= CAST(getvariable('dia') AS TIMESTAMP) - to_days(getvariable('dias_minimos'))
GROUP BY v.equipment_id, v.inicio_ventana;
