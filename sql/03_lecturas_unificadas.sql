-- Paso 03: unificar los dos formatos (D-09), convertir °F a °C (D-12) y marcar
-- el motivo de descarte de cada fila que no sirve (D-11, D-22). Una fila por fila cruda.
-- Todavía no se descarta ni deduplica nada: eso es el paso 04.
CREATE TABLE lecturas_staging AS
WITH unificadas AS (
    SELECT regexp_extract(filename, '[^/]+$') AS archivo,
           CASE WHEN equipment_id IS NOT NULL THEN 'viejo' ELSE 'nuevo' END AS formato,
           coalesce(equipment_id, asset_id) AS equipo_crudo,
           coalesce(ts, "timestamp") AS ts_txt,
           TRY_CAST(coalesce(ts, "timestamp") AS TIMESTAMP) AS ts,
           TRY_CAST(coalesce(vibracion_mm_s, vibration_mm_s) AS DOUBLE) AS vib_mm_s,
           TRY_CAST(coalesce(temperatura_c, temp) AS DOUBLE) AS temp_crudo,
           unidad_temp
    FROM raw_lecturas
)
SELECT archivo, formato, equipo_crudo,
       normalizar_id(equipo_crudo) AS equipment_id,
       ts_txt, ts, vib_mm_s, temp_crudo, unidad_temp,
       -- El formato viejo no declara unidad y se asume en °C. Una unidad desconocida da NULL
       -- y la frena el test 03_unidad_temp_conocida.
       CASE WHEN formato = 'viejo' THEN temp_crudo
            WHEN unidad_temp = 'C' THEN temp_crudo
            WHEN unidad_temp = 'F' THEN (temp_crudo - 32) * 5 / 9
       END AS temp_c,
       -- Cascada: el primer motivo que aplica.
       CASE WHEN ts IS NULL THEN 'ts_invalido'
            WHEN vib_mm_s IS NULL OR temp_crudo IS NULL THEN 'valor_no_numerico'
            WHEN normalizar_id(equipo_crudo) IS NULL
              OR normalizar_id(equipo_crudo) NOT IN (SELECT equipment_id FROM equipos)
                THEN 'equipo_fuera_del_maestro'
       END AS motivo_descarte
FROM unificadas;
