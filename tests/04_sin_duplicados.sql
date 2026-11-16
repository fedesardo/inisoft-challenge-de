-- R4(b): devuelve las claves (equipo, ts) que aparecen más de una vez en las lecturas limpias.
SELECT equipment_id, ts, count(*) AS veces
FROM lecturas
GROUP BY equipment_id, ts
HAVING count(*) > 1
ORDER BY equipment_id, ts
