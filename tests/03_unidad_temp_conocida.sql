-- D-12: devuelve las filas del formato nuevo cuya unidad de temperatura no es C ni F.
-- (El formato viejo no declara unidad y se asume en °C.)
SELECT archivo, equipo_crudo, ts_txt, temp_crudo, unidad_temp
FROM lecturas_staging
WHERE formato = 'nuevo'
  AND coalesce(unidad_temp, '<vacía>') NOT IN ('C', 'F')
ORDER BY archivo, equipo_crudo, ts_txt
