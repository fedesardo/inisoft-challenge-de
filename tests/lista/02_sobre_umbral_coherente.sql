-- Recalcula desde las lecturas limpias la sección sobre-umbral: cada día de la racha está sobre el umbral,
-- la mediana y las veces coinciden, no hay equipos sin datos, el orden y el tope se cumplen, y no falta
-- ningún equipo (cuando no hay más que el tope).
WITH diario AS (
    SELECT l.equipment_id, CAST(l.ts AS DATE) AS dia, median(l.vib_mm_s) AS med, any_value(e.umbral_vib_mm_s) AS umbral
    FROM limp.lecturas l JOIN limp.equipos e ON e.equipment_id = l.equipment_id
    GROUP BY l.equipment_id, CAST(l.ts AS DATE)
),
esperado AS (
    SELECT DISTINCT equipment_id AS equipo
    FROM (SELECT *, count_if(med > umbral) OVER (PARTITION BY equipment_id ORDER BY dia
                        RANGE BETWEEN to_days(getvariable('dias_seguidos') - 1) PRECEDING AND CURRENT ROW) AS n
          FROM diario)
    WHERE med > umbral AND n = getvariable('dias_seguidos')
      AND dia >= CAST(getvariable('cierre') AS DATE) - CAST(getvariable('dias_recientes') - 1 AS INTEGER)
      AND equipment_id NOT IN (SELECT equipo FROM sin_datos)
),
s AS (SELECT * FROM su_final)
SELECT equipo, 'más equipos que max_equipos' AS problema FROM s WHERE puesto > getvariable('max_equipos_su')
UNION ALL
SELECT equipo, 'el equipo está también en sin datos' FROM s WHERE equipo IN (SELECT equipo FROM sin_datos)
UNION ALL
SELECT s.equipo, 'un día de la racha no está sobre el umbral o no tiene lecturas'
FROM s
WHERE (SELECT count_if(d.med > d.umbral) FROM diario d
        WHERE d.equipment_id = s.equipo AND d.dia BETWEEN s.desde AND s.ultimo_dia) <> date_diff('day', s.desde, s.ultimo_dia) + 1
   OR s.dias_seguidos <> date_diff('day', s.desde, s.ultimo_dia) + 1
   OR s.dias_seguidos < getvariable('dias_seguidos')
UNION ALL
SELECT s.equipo, 'mediana del último día o veces sobre el umbral no coincide con el recálculo'
FROM s JOIN diario d ON d.equipment_id = s.equipo AND d.dia = s.ultimo_dia
WHERE abs(s.mediana_ultimo_dia - round(d.med, 4)) > 1e-9
   OR abs(s.veces_sobre_umbral - round(d.med / d.umbral, 2)) > 1e-9
UNION ALL
SELECT equipo, 'no está ordenada de mayor a menor'
FROM (SELECT equipo, veces_sobre_umbral, lag(veces_sobre_umbral) OVER (ORDER BY puesto) AS anterior FROM s)
WHERE anterior IS NOT NULL AND veces_sobre_umbral > anterior
UNION ALL
SELECT equipo, 'falta en sobre-umbral un equipo con racha activa'
FROM esperado
WHERE equipo NOT IN (SELECT equipo FROM s) AND (SELECT count(*) FROM esperado) <= getvariable('max_equipos_su')
