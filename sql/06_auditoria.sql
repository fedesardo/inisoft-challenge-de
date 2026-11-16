-- Paso 06: auditoría. Qué entra, qué sale y por qué (R4a).
-- "entran" sale de las tablas crudas, "quedan" de las tablas limpias y "salen" del detalle
-- de descartes: tres fuentes distintas, para que el test de cuadre compare cosas independientes.

-- Detalle: una fila por cada fila que sale (responde a "cuáles", D-11 y D-17).
CREATE TABLE descartes AS
SELECT 'lecturas' AS fuente, archivo AS origen, equipo_crudo, ts_txt AS momento,
       motivo_descarte AS motivo
FROM lecturas_staging
WHERE motivo_descarte IS NOT NULL
UNION ALL
SELECT 'lecturas', archivo, equipo_crudo, ts_txt, 'duplicado'
FROM lecturas_duplicadas
UNION ALL
SELECT 'ot', nro_ot, equipo_crudo, fecha_apertura_txt, motivo
FROM ot_descartadas;

-- Resumen: entran, salen (por motivo), quedan y datos informativos que no cambian el cuadre.
-- La columna explicacion dice en palabras qué significa cada fila (para quien lee el CSV o la consola).
CREATE TABLE auditoria AS
SELECT *,
       CASE WHEN concepto = 'entran' THEN 'Leídas de los archivos crudos'
            WHEN concepto = 'quedan' THEN 'Limpias, siguen en el pipeline'
            WHEN motivo = 'duplicado' THEN 'Lectura repetida (queda la de mayor vibración)'
            WHEN motivo = 'equipo_fuera_del_maestro' THEN 'Equipo que no está en equipos.csv (ej. EQ-TEST-01)'
            WHEN motivo = 'ts_invalido' THEN 'Fecha y hora ilegibles'
            WHEN motivo = 'valor_no_numerico' THEN 'Vibración o temperatura no numérica'
            WHEN motivo = 'fecha_invalida' THEN 'Fecha de la OT ilegible'
            WHEN motivo = 'ids_normalizados' THEN 'IDs sucios corregidos (eq-117 pasa a EQ-117)'
            WHEN motivo = 'temp_convertida_de_F' THEN 'Temperaturas pasadas de °F a °C'
            WHEN motivo LIKE 'tipo_%' THEN 'OT de tipo ' || replace(replace(motivo, 'tipo_', ''), '_', ' ')
            ELSE ''
       END AS explicacion
FROM (
SELECT 'lecturas' AS fuente, 'entran' AS concepto, '' AS motivo, count(*) AS filas
FROM raw_lecturas
UNION ALL
SELECT 'lecturas', 'salen', motivo, count(*) FROM descartes WHERE fuente = 'lecturas' GROUP BY motivo
UNION ALL
SELECT 'lecturas', 'quedan', '', count(*) FROM lecturas
UNION ALL
SELECT 'lecturas', 'informativo', 'ids_normalizados', count(*)
FROM lecturas_staging WHERE equipo_crudo <> equipment_id
UNION ALL
SELECT 'lecturas', 'informativo', 'temp_convertida_de_F', count(*)
FROM lecturas_staging WHERE motivo_descarte IS NULL AND unidad_temp = 'F'
UNION ALL
SELECT 'ot', 'entran', '', count(*) FROM raw_ot
UNION ALL
SELECT 'ot', 'salen', motivo, count(*) FROM descartes WHERE fuente = 'ot' GROUP BY motivo
UNION ALL
SELECT 'ot', 'quedan', '', count(*) FROM ot
UNION ALL
SELECT 'ot', 'informativo', 'ids_normalizados', count(*)
FROM ot_staging WHERE equipo_crudo <> equipment_id
UNION ALL
SELECT 'ot', 'informativo', 'tipo_' || tipo, count(*) FROM ot GROUP BY tipo
);
