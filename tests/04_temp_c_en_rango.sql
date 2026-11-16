-- D-23: devuelve las lecturas con temperatura vacía o fuera de [0, 120] °C.
-- El 120 queda sobre el máximo real del mes (95,8) y el umbral más alto del maestro (110),
-- y bajo el menor valor en °F sin convertir observado (126,7).
SELECT equipment_id, ts, temp_c, formato, archivo
FROM lecturas
WHERE temp_c IS NULL OR temp_c NOT BETWEEN 0 AND 120
ORDER BY equipment_id, ts
