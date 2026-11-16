-- Paso 07: exportar a salida/ (pipeline.py corre desde la raíz del repo, así que la ruta es relativa).
-- Todo con ORDER BY para que dos corridas den archivos idénticos (R1).
COPY (SELECT * FROM lecturas ORDER BY equipment_id, ts)
    TO 'salida/lecturas.parquet' (FORMAT parquet);

COPY (SELECT * FROM equipos ORDER BY equipment_id)
    TO 'salida/equipos.parquet' (FORMAT parquet);

COPY (SELECT * FROM ot ORDER BY nro_ot)
    TO 'salida/ot.parquet' (FORMAT parquet);

COPY (SELECT * FROM auditoria
      ORDER BY fuente,
               CASE concepto WHEN 'entran' THEN 1 WHEN 'salen' THEN 2
                             WHEN 'quedan' THEN 3 ELSE 4 END,
               motivo)
    TO 'salida/auditoria.csv' (FORMAT csv, HEADER);

COPY (SELECT * FROM descartes ORDER BY fuente, motivo, origen, equipo_crudo, momento)
    TO 'salida/descartes.csv' (FORMAT csv, HEADER);
