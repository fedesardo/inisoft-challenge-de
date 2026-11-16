-- Anti-fuga: lo único que ven las reglas. Datos con fecha estrictamente anterior al corte
-- (corte = día evaluado + 1, a las 00:00). Las reglas no leen nunca las tablas completas.
CREATE OR REPLACE TEMP TABLE vista_lecturas AS
SELECT equipment_id, ts, vib_mm_s, temp_c
FROM limp.lecturas
WHERE ts < CAST(getvariable('corte') AS TIMESTAMP);

CREATE OR REPLACE TEMP TABLE vista_ot AS
SELECT equipment_id, fecha_apertura
FROM limp.ot
WHERE fecha_apertura < CAST(getvariable('corte') AS TIMESTAMP);

CREATE OR REPLACE TEMP TABLE vista_equipos AS
SELECT equipment_id, umbral_vib_mm_s, umbral_temp_c
FROM limp.equipos;
