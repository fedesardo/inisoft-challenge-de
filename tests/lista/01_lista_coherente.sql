-- Devuelve las filas que rompen una regla de la lista. Recalcula la evidencia desde las lecturas
-- limpias (no desde las tablas del backtest) y la compara con lo que dice salida/lista.csv.
WITH l AS (SELECT * FROM lista_final)
SELECT equipo, 'más equipos que max_equipos' AS problema FROM l WHERE puesto > getvariable('max_equipos')
UNION ALL
SELECT equipo, 'el equipo está también en sin datos' FROM l WHERE equipo IN (SELECT equipo FROM sin_datos)
UNION ALL
SELECT equipo, 'el equipo no tiene lecturas en las últimas 24 h'
FROM l WHERE NOT EXISTS (SELECT 1 FROM limp.lecturas x WHERE x.equipment_id = l.equipo
                          AND x.ts > CAST(getvariable('cierre') AS TIMESTAMP) - INTERVAL 24 HOUR)
UNION ALL
-- Sin datos de verdad: ninguna lectura en las horas indicadas.
SELECT equipo, 'figura sin datos pero tiene lecturas recientes'
FROM sin_datos s WHERE EXISTS (SELECT 1 FROM limp.lecturas x WHERE x.equipment_id = s.equipo
                                AND x.ts >= CAST(getvariable('cierre') AS TIMESTAMP) - to_hours(getvariable('horas_sin_lecturas')))
UNION ALL
-- Veces sobre el normal: normal recalculado con la mediana de las lecturas de la ventana de ese día.
SELECT l.equipo, 'veces sobre el normal no coincide con el recálculo'
FROM l
JOIN bt_normales n ON n.equipment_id = l.equipo AND n.dia = l.desde
WHERE abs(l.veces_sobre_normal - round(
        (SELECT CASE l.senal WHEN 'vib' THEN median(x.vib_mm_s) ELSE median(x.temp_c) END
           FROM limp.lecturas x
          WHERE x.equipment_id = l.equipo
            AND x.ts > CAST(getvariable('cierre') AS TIMESTAMP) - INTERVAL 24 HOUR)
        / (SELECT CASE l.senal WHEN 'vib' THEN median(x.vib_mm_s) ELSE median(x.temp_c) END
             FROM limp.lecturas x
            WHERE x.equipment_id = l.equipo AND x.ts >= n.inicio_ventana
              AND x.ts < CAST(l.desde AS TIMESTAMP)), 2)) > 1e-9
UNION ALL
SELECT equipo, 'no está ordenada de mayor a menor desviación'
FROM (SELECT equipo, puesto, veces_sobre_normal,
             lag(veces_sobre_normal) OVER (ORDER BY puesto) AS anterior FROM l)
WHERE anterior IS NOT NULL AND veces_sobre_normal > anterior
UNION ALL
-- Una alerta real supera k × normal en alguna lectura del día de inicio (no se puede citar un "desde" sin evidencia).
SELECT l.equipo, 'sin lecturas sobre k × normal el día "desde"'
FROM l
JOIN bt_normales n ON n.equipment_id = l.equipo AND n.dia = l.desde
WHERE NOT EXISTS (
    SELECT 1 FROM limp.lecturas x
    WHERE x.equipment_id = l.equipo AND x.ts >= CAST(l.desde AS TIMESTAMP) AND x.ts < CAST(l.desde AS TIMESTAMP) + INTERVAL 1 DAY
      AND CASE l.senal WHEN 'vib' THEN x.vib_mm_s > getvariable('k') * n.normal_vib
                       ELSE x.temp_c > getvariable('k') * n.normal_temp END)
