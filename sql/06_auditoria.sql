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
       CASE WHEN concepto = 'entran' THEN 'Filas leídas de los archivos crudos'
            WHEN concepto = 'quedan' THEN 'Filas limpias que siguen en el pipeline'
            WHEN motivo = 'duplicado' THEN 'Misma lectura (equipo y hora) repetida: se conserva la de mayor vibración (D-10)'
            WHEN motivo = 'equipo_fuera_del_maestro' THEN 'El equipo no figura en equipos.csv (ej. EQ-TEST-01): se descarta (D-11, D-17)'
            WHEN motivo = 'ts_invalido' THEN 'La fecha y hora no se pueden leer: se descarta (D-22)'
            WHEN motivo = 'valor_no_numerico' THEN 'La vibración o la temperatura no es un número: se descarta (D-22)'
            WHEN motivo = 'fecha_invalida' THEN 'La fecha de la OT no se puede leer: se descarta (D-22)'
            WHEN motivo = 'ids_normalizados' THEN 'IDs que venían sucios y se corrigieron (ej. eq-117 pasa a EQ-117): no se pierde nada'
            WHEN motivo = 'temp_convertida_de_F' THEN 'Temperaturas que venían en °F y se pasaron a °C (D-12)'
            WHEN motivo LIKE 'tipo_%' THEN 'OT de este tipo, ya con los nombres unificados (D-18)'
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
