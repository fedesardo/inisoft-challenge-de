-- Caso EQ-209: OT 40262 el 20/02 a las 12:30 y falla el 27/02. Tras esa OT el normal solo puede usar
-- lecturas posteriores a las 12:30 del 20/02 y anteriores al día evaluado. Solo aplica si el drop
-- trae esa OT y lecturas de EQ-209 hasta el 27/02.
WITH hay_ot AS (
    SELECT 1 FROM limp.ot
    WHERE equipment_id = 'EQ-209' AND fecha_apertura = TIMESTAMP '2026-02-20 12:30:00'
      -- y el drop cubre los días que el test revisa: lecturas de EQ-209 desde antes del 15/02 (para que
      -- el 22/02 tenga 7 días de historia y se evalúe) hasta el 27/02. Con un drop de otro período
      -- o que corta antes (por ejemplo, un export de OT acumulado), el test no aplica.
      AND EXISTS (SELECT 1 FROM limp.lecturas WHERE equipment_id = 'EQ-209' AND ts < TIMESTAMP '2026-02-15 00:00:00')
      AND EXISTS (SELECT 1 FROM limp.lecturas WHERE equipment_id = 'EQ-209' AND ts >= TIMESTAMP '2026-02-27 00:00:00')
)
SELECT n.dia, n.equipment_id, 'EQ-209 evaluado el 21/02, con menos de 1 día desde la OT' AS problema
FROM bt_normales n, hay_ot
WHERE n.equipment_id = 'EQ-209' AND n.dia = DATE '2026-02-21'
UNION ALL
SELECT n.dia, n.equipment_id, 'EQ-209 usa lecturas anteriores a la OT del 20/02 12:30 o del día evaluado'
FROM bt_normales n, hay_ot
WHERE n.equipment_id = 'EQ-209' AND n.dia BETWEEN DATE '2026-02-22' AND DATE '2026-02-27'
  AND (n.min_ts_usada < TIMESTAMP '2026-02-20 12:30:00' OR n.max_ts_usada >= CAST(n.dia AS TIMESTAMP))
UNION ALL
SELECT DATE '2026-02-22', 'EQ-209', 'falta el día 22/02 o su ventana no arranca en la OT'
FROM hay_ot
WHERE NOT EXISTS (SELECT 1 FROM bt_normales n
                   WHERE n.equipment_id = 'EQ-209' AND n.dia = DATE '2026-02-22'
                     AND n.inicio_ventana = TIMESTAMP '2026-02-20 12:30:00')
UNION ALL
-- Con el normal reiniciado, el 26/02 (6 días después de la OT) tiene que durar menos de 7 días.
SELECT n.dia, n.equipment_id, 'EQ-209 el 26/02 usa más de lo posterior a la OT'
FROM bt_normales n, hay_ot
WHERE n.equipment_id = 'EQ-209' AND n.dia = DATE '2026-02-26'
  AND n.inicio_ventana <> TIMESTAMP '2026-02-20 12:30:00'
