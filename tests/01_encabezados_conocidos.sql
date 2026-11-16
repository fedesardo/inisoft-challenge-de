-- D-09: devuelve los archivos cuyo encabezado no es ninguno de los dos formatos conocidos.
SELECT archivo, cabecera
FROM encabezados
WHERE cabecera NOT IN (
    'equipment_id,ts,vibracion_mm_s,temperatura_c',
    'asset_id,timestamp,vibration_mm_s,temp,unidad_temp'
)
ORDER BY archivo
