-- R4(a): devuelve las fuentes donde entran no es igual a quedan + salen.
SELECT fuente, entran, salen, quedan, entran - salen - quedan AS diferencia
FROM (
    SELECT fuente,
           coalesce(sum(filas) FILTER (WHERE concepto = 'entran'), 0) AS entran,
           coalesce(sum(filas) FILTER (WHERE concepto = 'salen'), 0) AS salen,
           coalesce(sum(filas) FILTER (WHERE concepto = 'quedan'), 0) AS quedan
    FROM auditoria
    GROUP BY fuente
)
WHERE entran - salen - quedan <> 0
ORDER BY fuente
