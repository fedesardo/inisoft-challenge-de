-- Paso 04: deduplicar (D-10). De cada par (equipo, ts) repetido se conserva la fila de mayor
-- vibración. Los empates se desempatan por archivo y temperatura para que dos corridas den lo mismo.
CREATE TABLE lecturas_ranked AS
SELECT *,
       row_number() OVER (
           PARTITION BY equipment_id, ts
           ORDER BY vib_mm_s DESC, archivo, temp_c
       ) AS rn
FROM lecturas_staging
WHERE motivo_descarte IS NULL;

CREATE TABLE lecturas AS
SELECT equipment_id, ts, vib_mm_s, temp_c, formato, archivo
FROM lecturas_ranked
WHERE rn = 1;

-- Las filas que salen por repetidas, para la auditoría.
CREATE TABLE lecturas_duplicadas AS
SELECT archivo, equipo_crudo, ts_txt
FROM lecturas_ranked
WHERE rn > 1;

DROP TABLE lecturas_ranked;
