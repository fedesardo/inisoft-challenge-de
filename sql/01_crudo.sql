-- Paso 01: leer drop/ tal cual (solo lectura) y dejar copias crudas en la base.
-- Todo como texto (all_varchar): así ningún valor raro se esconde por adivinar tipos.
-- La carpeta la fija pipeline.py con SET VARIABLE drop_dir (por defecto drop/).

-- Misma regla de normalización de IDs que H-13 y D-17: recortar espacios, mayúsculas, guion.
CREATE OR REPLACE MACRO normalizar_id(x) AS
    upper(regexp_replace(trim(x), '^(?i)eq-?', 'EQ-'));

CREATE TABLE raw_lecturas AS
SELECT * FROM read_csv(getvariable('drop_dir') || '/lecturas-*.csv',
    union_by_name = true, filename = true, all_varchar = true);

CREATE TABLE raw_equipos AS
SELECT * FROM read_csv(getvariable('drop_dir') || '/equipos.csv', all_varchar = true);

CREATE TABLE raw_ot AS
SELECT * FROM read_csv(getvariable('drop_dir') || '/ordenes-de-trabajo.csv', all_varchar = true);

-- Primera línea de cada archivo de lecturas (los encabezados traen un retorno de carro al final).
CREATE TABLE encabezados AS
SELECT regexp_extract(filename, '[^/]+$') AS archivo,
       rtrim(split_part(content, chr(10), 1), chr(13)) AS cabecera
FROM read_text(getvariable('drop_dir') || '/lecturas-*.csv');
