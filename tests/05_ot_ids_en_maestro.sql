-- D-17: devuelve las OT conservadas cuyo equipo no cruza con el maestro.
SELECT o.nro_ot, o.equipo_crudo, o.equipment_id
FROM ot o
ANTI JOIN equipos e USING (equipment_id)
ORDER BY o.nro_ot
