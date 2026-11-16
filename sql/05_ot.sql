-- Paso 05: órdenes de trabajo. IDs normalizados (D-17) y tipos unificados (D-18).
-- Falla (D-20): la descripción contiene alguna frase de config/frases-falla.txt (una por línea).
-- El tipo no se usa para decidir. Rutas relativas a la raíz del repo (pipeline.py hace chdir).
CREATE TABLE frases_falla AS
SELECT trim(unnest(string_split(rtrim(replace(content, chr(13), ''), chr(10)), chr(10)))) AS frase
FROM read_text('config/frases-falla.txt');

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
       EXISTS (SELECT 1 FROM frases_falla f
               WHERE f.frase <> '' AND contains(lower(coalesce(raw_ot.descripcion, '')), lower(f.frase))) AS es_falla,
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
       tipo_crudo, tipo, descripcion, es_falla
FROM ot_staging
WHERE motivo_descarte IS NULL;

CREATE TABLE ot_descartadas AS
SELECT nro_ot, equipo_crudo, fecha_apertura_txt, motivo_descarte AS motivo
FROM ot_staging
WHERE motivo_descarte IS NOT NULL;
