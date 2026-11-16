---
name: normalizar-ot
description: Normaliza ordenes-de-trabajo.csv (IDs de equipo, fechas, tipos) y marca qué OT son fallas según la lista config/frases-falla.txt. Usala al recibir un drop nuevo, al cambiar sql/05_ot.sql o config/frases-falla.txt, o cuando una OT no cruza con equipos.csv o trae un tipo desconocido.
---

# Normalizar órdenes de trabajo

Paso `sql/05_ot.sql` del pipeline. Entrada: `ordenes-de-trabajo.csv` (columnas `nro_ot, equipo, fecha_apertura, fecha_cierre, tipo, descripcion`). Salida: tablas `ot` y `ot_descartadas` en `salida/limpieza.duckdb`.

## Reglas
- **ID de equipo (D-17):** recortar espacios, pasar a mayúsculas e insertar el guion: `eq-117`, `EQ103`, ` EQ-101` pasan a `EQ-117`, `EQ-103`, `EQ-101`. Si tras normalizar no existe en `equipos.csv`, la OT se descarta con motivo `equipo_fuera_del_maestro` y se cuenta en la auditoría.
- **Fechas:** formato `dd/mm/aaaa hh:mm`. Una fecha ilegible descarta la OT (`fecha_invalida`); no se adivina.
- **Tipo (D-18):** `PREV`/`Preventivo` pasan a `preventivo`; `CORR`/`Correctivo` a `correctivo`; vacío a `sin_tipo`. Cualquier otro valor queda `desconocido`.

## Definición de falla (D-20)
Una OT es **falla** si su descripción contiene alguna frase de `config/frases-falla.txt` (una por línea, sin distinguir mayúsculas). Es una "falla con parada": el equipo se detuvo o se rompió. **El tipo no se usa para decidir**, porque el cliente avisó que no siempre lo cargan.

Ejemplos (OT reales del drop de febrero, salvo indicación):
| OT | Texto | ¿Falla? | Por qué |
|---|---|---|---|
| 40252 | "Disparo x alta temp… Equipo detenido ~8hs" (sin tipo) | Sí | Contiene `disparo` y `detenido`; el tipo vacío no importa |
| 40256 | "…se para la bomba de urgencia…" (Correctivo) | Sí | Contiene `se para` y `urgencia` |
| 40250 | "Revisión de cableado… Sin falla." (sin tipo) | No | La palabra `falla` no está en la lista a propósito: aparece en "sin falla" |
| 40246 | "Vibración alta… equipo sigue en servicio." (Correctivo) | No | Correctivo, pero no se detuvo |
| 40254 | "…cambio de rodamiento en próxima parada." (PREV) | No | `parada` suelta no está en la lista: aparece en "próxima parada" |

Con el drop de febrero da exactamente 5 fallas (EQ-107, 214, 116, 112, 209).

## Cuidados
- No agregar líneas vacías a `config/frases-falla.txt`: una línea vacía está contenida en cualquier texto y marcaría todas las OT como falla. El test `tests/05_frases_falla_validas.sql` corta el pipeline si pasa.
- No agregar palabras sueltas como `falla`, `parada` o `ruido`: generan falsos positivos.
- Límites conocidos: una parada planificada que use una frase de la lista sería falso positivo; una falla que no detiene el equipo queda fuera.

## Procesar un drop nuevo
1. Correr `make run DROP=<carpeta>`; la carpeta no se modifica. Este paso (05) corre después de los de lecturas: si el pipeline se corta antes por un test de lecturas (encabezado o unidad desconocidos), las OT no se procesan. Resolvelo primero con la skill `leer-lecturas` y volvé a correr.
2. Mirar la auditoría de OT en la consola (entran = quedan + descartadas) y la tabla `ot_descartadas`.
3. Si aparece tipo `desconocido`, un ID huérfano o más/menos fallas de lo esperado: frená, mostrale al usuario las OT tal cual y preguntá antes de tocar el SQL o la lista. Registrar el cambio en `DECISIONES.md`.
4. Listar las OT con `es_falla` para revisión humana (número, equipo, texto).

Drop mínimo de ejemplo en `tests/fixtures/` (OT inventadas; no son datos del cliente).
