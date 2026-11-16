-- Paso 02: maestro de equipos tipado. Es la lista oficial de qué equipos existen (D-11).
CREATE TABLE equipos AS
SELECT normalizar_id(equipment_id) AS equipment_id,
       tipo,
       planta,
       CAST(umbral_vib_mm_s AS DOUBLE) AS umbral_vib_mm_s,
       CAST(umbral_temp_c AS DOUBLE) AS umbral_temp_c
FROM raw_equipos;
