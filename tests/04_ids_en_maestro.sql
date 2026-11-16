-- D-11: devuelve los IDs de las lecturas limpias que no cruzan con el maestro.
SELECT l.equipment_id, count(*) AS filas
FROM lecturas l
ANTI JOIN equipos e USING (equipment_id)
GROUP BY l.equipment_id
ORDER BY l.equipment_id
