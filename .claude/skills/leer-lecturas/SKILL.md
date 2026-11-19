---
name: leer-lecturas
description: Lee, unifica y limpia los archivos lecturas-*.csv de telemetría (vibración y temperatura) de los dos sistemas de captura. Usala al recibir un drop nuevo, al cambiar sql/03 o sql/04, o ante un lecturas-*.csv con encabezados raros.
---

# Leer lecturas-*.csv

Los archivos `lecturas-*.csv` vienen en dos formatos. Se reconocen **solo por el encabezado** (primera línea), nunca por el nombre ni la fecha del archivo.

## Formatos

| Formato | Encabezado exacto | Unidad de temperatura |
|---|---|---|
| viejo | `equipment_id,ts,vibracion_mm_s,temperatura_c` | °C (no la declara, se asume) |
| nuevo | `asset_id,timestamp,vibration_mm_s,temp,unidad_temp` | columna `unidad_temp`: `C` o `F` |

Un drop puede traer un solo formato (desde el 11/02 el cliente manda solo el nuevo): `sql/01_crudo.sql` agrega vacías las columnas del otro, no hay que tocar nada.

Drop mínimo de ejemplo en `tests/fixtures/` (inventado; no son datos del cliente).

## Reglas
- **Vibración:** mm/s en ambos formatos, sin conversión.
- **Temperatura:** `C` queda igual; `F` se convierte con `(F − 32) × 5 / 9` fila por fila (D-12).
- **IDs:** se normalizan (recortar espacios, mayúsculas, `EQ-`); los que no están en `equipos.csv` se descartan (D-11).
- **Duplicados:** de cada par (equipo, ts) repetido se conserva la fila de mayor vibración (D-10).
- Lo descartado se cuenta en la auditoría (`salida/auditoria.csv`), nunca se pierde en silencio.

## Formato desconocido
No adivinar ni "arreglar" el archivo. El test `tests/01_encabezados_conocidos.sql` o el de
unidad (`03_unidad_temp_conocida.sql`) corta el pipeline con código 1 y lista los archivos o
filas culpables. Frená, mostrale al usuario el mensaje tal cual (archivo y encabezado o
unidad) y preguntá cómo se interpreta. Solo después se agrega el formato al SQL (columnas en `sql/01_crudo.sql` y `sql/03`) y a su test,
y se registra en `DECISIONES.md`.

## Procesar un drop nuevo
1. Verificar la carpeta: debe tener `lecturas-*.csv`, `equipos.csv` y `ordenes-de-trabajo.csv`.
   Mirar el encabezado de cada lectura (`head -1`) y contarlos por formato.
2. Correr `make run DROP=<carpeta>`. Es de solo lectura sobre el drop; escribe solo en `salida/`.
3. Revisar los tests: la corrida termina en `OK` o con `TEST FALLÓ` / `ERROR` (código 1). El
   historial queda en `salida/corridas.csv`.
4. Resumir qué cambió respecto del drop anterior: archivos por formato, filas que entran,
   salen (por motivo) y quedan, duplicados, filas en °F, y cualquier test que falló.

No modificar nunca `drop/` ni la carpeta del cliente.
