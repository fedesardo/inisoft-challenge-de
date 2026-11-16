-- D-20: devuelve un problema si config/frases-falla.txt no tiene frases o tiene líneas vacías.
-- Una línea vacía está contenida en cualquier texto y marcaría todas las OT como falla.
SELECT 'archivo_sin_frases' AS problema, 0 AS linea
WHERE (SELECT count(*) FROM frases_falla WHERE frase <> '') = 0
UNION ALL
SELECT 'linea_vacia', row_number() OVER ()
FROM frases_falla
QUALIFY frase = ''
