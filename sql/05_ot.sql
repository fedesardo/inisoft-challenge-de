-- Paso 05: órdenes de trabajo. IDs normalizados (D-17) y tipos unificados (D-18).
-- Qué cuenta como falla (D-20) NO se decide acá: es un parámetro del criterio.
CREATE TABLE ot_staging AS
SELECT nro_ot,
       equipo AS equipo_crudo,
       normalizar_id(equipo) AS equipment_id,
       fecha_apertura AS fecha_apertura_txt,
       TRY_STRPTIME(fecha_apertura, '%d/%m/%Y %H:%M') AS fecha_apertura,
       TRY_STRPTIME(fecha_cierre, '%d/%m/%Y %H:%M') AS fecha_cierre,
       tipo AS tipo_crudo,
       CASE WHEN lower(trim(tipo)) IN ('prev', 'preventivo') THEN 'preventivo'
            WHEN lower(trim(tipo)) IN ('corr', 'correctivo') THEN 'correctivo'
            WHEN tipo IS NULL OR trim(tipo) = '' THEN 'sin_tipo'
            ELSE 'desconocido'
       END AS tipo,
       descripcion,
       -- Cascada: el primer motivo que aplica (D-17, D-22).
       CASE WHEN TRY_STRPTIME(fecha_apertura, '%d/%m/%Y %H:%M') IS NULL
              OR (nullif(trim(fecha_cierre), '') IS NOT NULL
                  AND TRY_STRPTIME(fecha_cierre, '%d/%m/%Y %H:%M') IS NULL)
                THEN 'fecha_invalida'
            WHEN normalizar_id(equipo) IS NULL
              OR normalizar_id(equipo) NOT IN (SELECT equipment_id FROM equipos)
                THEN 'equipo_fuera_del_maestro'
       END AS motivo_descarte
FROM raw_ot;

CREATE TABLE ot AS
SELECT nro_ot, equipo_crudo, equipment_id, fecha_apertura, fecha_cierre,
       tipo_crudo, tipo, descripcion
FROM ot_staging
WHERE motivo_descarte IS NULL;

CREATE TABLE ot_descartadas AS
SELECT nro_ot, equipo_crudo, fecha_apertura_txt, motivo_descarte AS motivo
FROM ot_staging
WHERE motivo_descarte IS NOT NULL;
