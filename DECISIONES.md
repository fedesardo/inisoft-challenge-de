# Decisiones

Cada decisión con su contexto, la alternativa descartada y la evidencia que la sostiene.

<!-- Plantilla:
## D-NN · Título
- **Contexto:**
- **Qué decidí:**
- **Qué descarté y por qué:**
- **Consecuencia:**
- **Evidencia:**
-->

## D-01 · `drop/` se versiona en el repo
- **Contexto:** el pipeline tiene que correr con un solo comando (`make run`). Los datos crudos del cliente pesan 4.6 MB.
- **Qué decidí:** versionar `drop/` tal como llegó, para que `make run` funcione en un clon limpio. Condición: el repo es privado y se entrega solo al evaluador, porque son datos del cliente.
- **Qué descarté y por qué:** dejar `drop/` fuera del repo y pedir que se descargue aparte. Agrega un paso manual y rompe el "un solo comando".
- **Consecuencia:** el repo no se puede publicar. Si se hiciera público, habría que sacar `drop/` y reescribir el historial.
- **Evidencia:** `du -sh drop` = 4.6 MB. `CHALLENGE.md`, sección Restricciones ("Un comando levanta todo").

## D-02 · `PLAN.md` queda fuera del repo
- **Contexto:** `PLAN.md` son notas de trabajo personales para organizar el challenge.
- **Qué decidí:** excluirlo con `.gitignore`. La evidencia del proceso está en `SPEC.md`, `DECISIONES.md`, `AI-LOG.md` y los commits.
- **Qué descarté y por qué:** versionarlo. Mezcla planificación personal con la entrega y duplica lo que ya documentan los otros archivos.
- **Consecuencia:** quien clone el repo no ve el plan inicial; el razonamiento tiene que quedar completo en los documentos versionados.
- **Evidencia:** el propio `PLAN.md` dice "No es parte de la entrega".

## D-03 · Permisos `allow` explícitos en `.claude/settings.json`, sin `git *`
- **Contexto:** cada paso cierra con un commit y el pipeline corre con `uv run`. Pedir permiso para esos comandos en cada uso interrumpe el trabajo sin sumar control.
- **Qué decidí:** pre-aprobar solo `uv run *`, `git status`, `git diff *`, `git log *`, `git add *` y `git commit *`. Son los comandos que necesita el ciclo "correr → revisar → commitear". Todos actúan sobre el repo local y se pueden deshacer.
- **Qué descarté y por qué:** `git *`. También habilitaría comandos destructivos o con efecto hacia afuera sin pedir confirmación: `push` (publica datos del cliente, ver D-01), `reset --hard`, `clean -f` y `checkout --` (pierden trabajo sin commitear), `rebase` y `commit --amend` sobre historial ya revisado, `config` (podría cambiar el mail de autor). Esos siguen pidiendo confirmación caso por caso.
- **Consecuencia:** el flujo diario no pide permiso; cualquier otro comando, sí. Límite conocido: `uv run *` ejecuta código arbitrario (`uv run python -c ...`, `uv run bash`), así que no es una barrera de seguridad. La protección de `drop/` la siguen dando el deny y el `chmod` (ver AI-LOG, prueba de 3 capas).
- **Evidencia:** `.claude/settings.json`.

## D-04 · La lista semanal tiene como máximo 5 equipos
- **Contexto:** el cliente apagó un sistema de alertas que "avisaba todo el tiempo" (`README-del-cliente.txt`, `CHALLENGE.md`). El enunciado no fija cuántos equipos puede tener la lista. Más equipos suben la cobertura de fallas (recall) y bajan la precisión.
- **Qué decidí:** tope de 5 equipos (12,5% de los 40) como restricción de diseño, para que la lista siga siendo difícil de ignorar.
- **Qué descarté y por qué:** 10 equipos (25% de la flota, cerca de volver a "avisar todo"); sin tope (nada limita las falsas alarmas).
- **Consecuencia:** puede quedar afuera alguna falla real. El backtest tiene que reportar recall además de precisión, para que ese costo sea visible.
- **Evidencia:** razonamiento a partir del README del cliente. PENDIENTE TRAS PERFILADO: contrastar el 5 con la cantidad real de fallas del mes.

## D-05 · Backtest con corte diario y lista de 7 días
- **Contexto:** hay un solo mes de datos, así que hay pocas fechas posibles para simular la lista.
- **Qué decidí:** simular una lista cada día. En cada corte el criterio solo ve datos anteriores a esa fecha (sin fuga de información) y se compara con las fallas de las OT de los 7 días siguientes. La jefa recibe una sola lista semanal; el corte diario es solo para medir.
- **Qué descarté y por qué:** un corte por semana (~4 listas): imita el uso real pero da muy poca evidencia.
- **Consecuencia:** los ~20 cortes se solapan, así que no son independientes. Hay que decirlo en las limitaciones del resultado. La cantidad exacta de cortes depende de cuántos días tienen datos utilizables tras el cambio de sistema del 11/02.
- **Evidencia:** PENDIENTE TRAS PERFILADO (cantidad de cortes y de fallas).

## D-06 · El criterio de selección es un conjunto de reglas explicables, no un modelo ML
- **Contexto:** hay unas 115.000 lecturas, pero probablemente pocas fallas en las OT (estimación a confirmar). Un modelo aprende de ejemplos de falla, no de lecturas.
- **Qué decidí:** puntaje por reglas sobre vibración y temperatura (umbrales de `equipos.csv`, tendencia, persistencia). Cada equipo de la lista lleva escrita su razón.
- **Qué descarté y por qué:** un modelo estadístico. Con pocas fallas tiende a sobreajustar (anda bien en el pasado y mal en el futuro) y no explica sus decisiones, que es justo lo que le falló al sistema anterior.
- **Consecuencia:** las reglas hay que calibrarlas a mano y el riesgo de calibrar contra las mismas fallas que luego se miden es real; el backtest debe separar lo que se usa para calibrar de lo que se usa para medir.
- **Evidencia:** PENDIENTE TRAS PERFILADO (qué señales y qué pesos; cantidad de fallas).

## D-07 · Asunción: las fallas tienen un intervalo P-F detectable
- **Contexto:** la curva P-F describe el tiempo entre que la degradación se puede detectar (P) y la falla funcional (F). Ese intervalo es la ventana de anticipación del criterio.
- **Qué decidí:** asumir que antes de cada falla hay señal detectable en vibración o temperatura, y estimar el intervalo P-F mirando cuántos días antes de cada falla de las OT empezó a moverse la señal.
- **Qué descarté y por qué:** fijar la ventana a priori sin mirar los datos.
- **Consecuencia:** con pocas fallas el intervalo saldrá como un rango aproximado. Si es de horas, una lista semanal no sirve para esas fallas y hay que decirlo.
- **Evidencia:** PENDIENTE TRAS PERFILADO.

## D-08 · Un acierto exige al menos 2 días de anticipación
- **Contexto:** marcar un equipo que falla al día siguiente técnicamente anticipa la falla, pero no deja tiempo de programar la visita, conseguir repuestos y parar la máquina.
- **Qué decidí:** un equipo de la lista cuenta como acierto solo si falla entre 2 y 7 días después del corte. Es una asunción a confirmar con el cliente (Mauro o Julián).
- **Qué descarté y por qué:** 1 día (infla el número con avisos que no sirven en la práctica); 3 días o más (con pocas fallas casi nada contaría).
- **Consecuencia:** el resultado del backtest se ve peor, pero es más honesto con una jefa que ya desconfía de las alertas.
- **Evidencia:** razonamiento operativo; sin dato del cliente sobre tiempos reales de respuesta. Pendiente de confirmar.

## D-09 · Ingesta: unir los formatos por nombre y fallar si aparece un encabezado desconocido
- **Contexto:** las lecturas llegan en dos formatos con encabezados distintos (`equipment_id, ts, vibracion_mm_s, temperatura_c` hasta el 10/02; `asset_id, timestamp, vibration_mm_s, temp, unidad_temp` desde el 11/02). El cliente no documentó el cambio y el mes que viene podría traer un tercer formato.
- **Qué decidí:** leer todos los archivos con `union_by_name`, unificar las columnas con `coalesce` y **detener la ingesta con un error claro** si algún archivo trae un encabezado fuera de los dos conocidos.
- **Qué descarté y por qué:** (A) solo `coalesce`, sin verificación: un formato nuevo produciría NULL en silencio y señales inventadas o vacías, lo que R4 prohíbe; (B) un lector separado por formato: más código para el mismo resultado.
- **Consecuencia:** un formato nuevo frena el pipeline con un mensaje, y la skill de "leer un drop" (R10) tiene que explicar cómo agregar el mapeo.
- **Evidencia:** `docs/perfilado.md`, H-01 (10 archivos viejos y 20 nuevos, corte el 11/02, 115.065 filas) y la tabla de encabezados de la sección de preparación.

## D-10 · Duplicados: de cada par conflictivo se conserva la lectura de mayor vibración
- **Contexto:** el sistema viejo repite lecturas (misma clave equipo + timestamp). Son 229 pares, todos de exactamente 2 filas; solo 5 son idénticos y en 224 cambia la vibración (diferencia máxima 0,051 mm/s, mediana 0,014). La temperatura es igual en las dos copias de todos los pares. El sistema nuevo no tiene duplicados.
- **Qué decidí:** conservar, por cada clave repetida, la fila con mayor vibración (la temperatura es la misma). Las filas descartadas se cuentan para el cuadre de R4(a). En los 5 pares idénticos da igual cuál quede.
- **Qué descarté y por qué:** la primera fila (depende del orden de lectura y no es robusta); el promedio (inventa un valor que no está en el dato crudo, lo que R4 prohíbe); la de menor vibración (podría ocultar un pico real).
- **Consecuencia:** el criterio es determinista (dos corridas dan el mismo resultado, R1) y conservador: ante la duda no oculta una señal. Introduce un sesgo hacia arriba de hasta 0,051 mm/s, menos del 2 % del umbral más bajo (2,8 mm/s en turbinas).
- **Evidencia:** `docs/perfilado.md`, H-03.

## D-11 · Equipos desconocidos: se conservan solo los IDs del maestro y se reporta lo descartado
- **Contexto:** las lecturas incluyen un ID que no está en `equipos.csv`: `EQ-TEST-01` (48 filas, una por hora, 20/02 00:00 a 21/02 23:00, solo en el formato nuevo). Sus lecturas marcadas °C van de 3,7 a 149,7, un rango que ningún equipo real tiene (sin él, el máximo del mes es 95,8 °C). Parece una prueba de instalación del sistema nuevo.
- **Qué decidí:** quedarse solo con lecturas cuyo equipo figure en el maestro (lista blanca). Las filas descartadas por esta regla se cuentan, se reportan en el perfilado generado por el pipeline y entran en el cuadre de R4(a) como "inválidas descartadas".
- **Qué descarté y por qué:** excluir por nombre (`<> 'EQ-TEST-01'`): si el mes que viene aparece otro ID de prueba, entraría sin aviso. Excluir por temperatura mayor a 100 °C: el 100 es un número redondo sin respaldo (ver H-06), y el máximo real del mes (95,8 °C) queda muy cerca.
- **Consecuencia:** la regla sirve para cualquier drop futuro. Si llega un equipo legítimo que falta en el maestro, se descarta, pero queda a la vista en el reporte para que alguien lo note y actualice el maestro.
- **Evidencia:** `docs/perfilado.md`, H-06. Cuadre: 115.065 filas crudas = 114.788 limpias + 229 duplicados + 48 de `EQ-TEST-01`. Pregunta abierta al cliente: confirmar que `EQ-TEST-01` es un equipo de prueba.

## D-12 · Temperatura: convertir °F según `unidad_temp` y fallar si la unidad no es C ni F
- **Contexto:** el sistema nuevo mezcla °C y °F: 11.400 filas marcadas °F (14,9 % del nuevo), repartidas en los 40 equipos. Convertidas con (°F − 32) × 5/9, caen en el mismo rango y con la misma forma que las °C (mediana 65,2 °C contra 64,6 °C del sistema viejo). Sin convertir, el 14,92 % de las lecturas del nuevo superaría el umbral de temperatura.
- **Qué decidí:** convertir fila por fila según `unidad_temp`. Si aparece un valor de unidad distinto de `C` o `F`, el pipeline se detiene con un mensaje claro. El sistema viejo, que no declara unidad, se asume en °C (su rango 52–79 es coherente).
- **Qué descarté y por qué:** adivinar la unidad por el valor (falla en zonas ambiguas); descartar las filas °F (pierde el 14,9 % del sistema nuevo); agregar una verificación de rangos por tipo de equipo (compleja, requiere fijar un corte con poco margen frente al máximo real de 95,8 °C, y no se activa con los datos de hoy).
- **Consecuencia:** una unidad nueva (por ejemplo `K`) frena el pipeline en vez de pasar en silencio. Límite conocido: una fila marcada `C` que en realidad sea °F no se detectaría automáticamente; los rangos quedan visibles en el informe de perfilado para revisión humana.
- **Evidencia:** `docs/perfilado.md`, H-04 (y su gráfico `docs/graficos/h04-unidades.png`) y H-12.

## D-13 · Zona horaria: no corregir el desfase; dejarlo configurable
- **Contexto:** los timestamps no declaran zona horaria en ningún formato (todos de 19 caracteres, sin `Z` ni desfase). El ciclo diario de temperatura tiene su pico a las ~14:30 en el sistema viejo y a las ~17:30 en el nuevo: un corrimiento de unas 3 horas. Consulté con Mauro y me dijo que los archivos viejos y las OT están en hora de planta, que del sistema nuevo no sabe (el proveedor no entregó documentación) y que tomara la decisión que mejor pudiera justificar. La explicación más probable es que el nuevo esté 3 horas adelantado respecto de la planta (por ejemplo, guardando UTC), pero sigue siendo una inferencia nuestra, no un dato confirmado. Además la grilla de 15 minutos es continua en la frontera del 10/02 al 11/02, sin salto ni solape de 3 horas.
- **Qué decidí:** no corregir el dato (queda tal como llegó) y dejar el desfase como un parámetro de configuración con valor 0 por defecto. Se escribe como limitación conocida.
- **Qué descarté y por qué:** restar 3 horas a todo el sistema nuevo. Se apoya en una inferencia sin confirmar y, medido sobre los datos, crearía problemas concretos: 484 pares (equipo, momento) repetidos con el sistema viejo el 10/02 de 21:00 a 23:45, con valores distintos (diferencia promedio de vibración 0,1 mm/s) que habría que resolver con una regla nueva; las últimas 3 horas del mes quedarían sin datos (el último dato pasaría de 02/03 23:45 a 20:45); y 9.572 lecturas (12,5 % del sistema nuevo) cambiarían de día. Si la corrección está equivocada, además, corrompe el dato (viola "no inventa señales", R4).
- **Consecuencia:** el criterio trabaja con cortes y métricas diarias, así que 3 horas casi no cambian el resultado. Cualquier análisis por hora del día quedaría torcido hasta confirmar la zona horaria del sistema nuevo. Si se confirma, se corrige cambiando una línea de configuración y resolviendo los solapes.
- **Evidencia:** `docs/perfilado.md`, H-07 y su gráfico `docs/graficos/h07-ciclo-diario.png`; mediciones del efecto de una corrección de −3 h en esta decisión. Estado: el cliente respondió; la zona horaria del sistema nuevo sigue sin confirmarse y se asume sin corregir.

## D-14 · Huecos de lecturas: no imputar y avisar cuando un equipo se queda sin telemetría
- **Contexto:** faltan 412 lecturas de las 115.200 esperadas (40 equipos × 2.880): 220 en días con alguna fila y 192 en los dos días enteros que EQ-110 no reportó. Hay dos patrones: EQ-110 deja de reportar el 28/02 a las 08:45 y no vuelve (252 faltantes, sin OT que lo explique); y cinco equipos (EQ-107, 112, 116, 209, 214) tienen un único hueco de 8 h 15 min (32 lecturas) el mismo día de su falla con parada según las OT. La ausencia de lecturas coincide con equipos parados, así que es información y no ruido.
- **Qué decidí:** no rellenar los huecos (ni interpolando ni con ceros) y tratar el silencio prolongado de un equipo como un aviso aparte, "sin telemetría reciente", visible en el dashboard y el informe.
- **Qué descarté y por qué:** interpolar entre la lectura anterior y la siguiente (inventa señal justo cuando el equipo estuvo parado, lo que R4 prohíbe); rellenar con ceros (un cero parece un equipo sano); no hacer nada (se pierde el aviso de equipos que se callan, como EQ-110).
- **Consecuencia:** los promedios y medianas usan menos lecturas, lo cual sigue siendo válido. Hay que construir la detección del aviso. **Pendiente:** definir cuánto silencio cuenta como sospechoso (cantidad de horas sin lecturas respecto del último dato del drop); se cierra en el paso del criterio y se registra aquí.
- **Evidencia:** `docs/perfilado.md`, H-08 y su gráfico `docs/graficos/h08-huecos.png`. Pregunta abierta al cliente: si EQ-110 está fuera de servicio desde el 28/02.

## D-15 · Tolerancia de R4(c): ±0,5 % sobre la mediana de los cambios entre equipos, y se reportan los equipos que cambian más
- **Contexto:** R4(c) pide que la mediana de cada variable por equipo antes y después del cambio de sistema (11/02) quede dentro de una tolerancia. Con °F convertido, 31 de 40 equipos son estables (cambio máximo 1,61 % en vibración y 0,33 % en temperatura) y 9 cambian por eventos propios (degradación, sensor reemplazado, sensor trabado). Una tolerancia exigida equipo por equipo fallaría siempre por esos 9, que no son un defecto de ingesta.
- **Qué decidí:** el test mide la **mediana, entre los 40 equipos, del cambio porcentual** de la mediana de cada equipo (temperatura y vibración) y exige que esté dentro de ±0,5 %. Los equipos con cambio individual mayor a 2 % en vibración o 1 % en temperatura se **reportan** en el informe, sin hacer fallar el test. Estos dos límites de reporte son solo descriptivos.
- **Cómo se fijó el ±0,5 %:** entre el ruido normal y el error que se quiere atrapar. Ruido: la mediana del cambio entre equipos es −0,008 % en temperatura y 0,0 % en vibración. Error a detectar: si no se convirtiera °F, esa mediana sería +1,24 % en temperatura (+0,82 % en el equipo menos afectado). Con ±0,5 % quedan 0,5 puntos de margen sobre el ruido y 0,74 bajo el error. Con ±1 % el margen bajo el error era solo 0,24; con ±0,1 % el ruido de otro mes podría disparar falsas alarmas.
- **Qué descarté y por qué:** tolerancia por equipo (falla siempre por los 9 eventos reales); ±1 % (atrapa el error de °F, pero con margen mínimo); ±0,1 % (demasiado sensible al ruido); lista fija de excepciones por equipo (hay que mantenerla a mano).
- **Consecuencia:** el test detecta un cambio sistémico (una unidad o escala que mueva a toda la flota), que es lo que R4 vigila, y no castiga a un equipo que se degrada. No detecta un único equipo mal convertido. La mediana tolera hasta cerca de un 22 % de equipos con cambio (los 9 de hoy); si el mes que viene muchos más equipos cambian, el test fallaría y habría que revisar.
- **Limitación declarada:** calibrada con un solo mes de datos; la vibración no tiene un error de referencia propio como el de °F. Asunción propia, a ajustar con más meses; no requiere confirmación del cliente.
- **Riesgo aceptado (decidido el 16/11):** la limpieza (paso 04) se entregó **sin** el test de R4(c). Los controles que sí corren (encabezados, unidad C/F, rango 0–120 °C, duplicados, cuadre) no miden si el nivel de cada variable cambió entre sistemas. Con los datos de hoy no hay problema conocido: la mediana de los cambios es −0,008 % en temperatura y 0,0 % en vibración, dentro de ±0,5 %.
- **Qué se pierde:** si un drop futuro trae un cambio que mueva a toda la flota, el pipeline termina en código 0 y la lista se calcula con una señal torcida, sin aviso. Dos casos: (1) un cambio de escala o unidad en vibración (por ejemplo de mm/s a otra unidad): ningún test actual lo ve, y el criterio marcaría a todos los equipos o a ninguno; (2) un cambio de temperatura que no llegue a salir de 0–120 °C (D-23 cubre solo el caso de °F sin convertir a niveles normales de operación). Hasta cerrarlo, el requisito R4(c) de la SPEC queda sin cubrir.
- **Qué test haría falta:** `tests/04_nivel_estable_entre_sistemas.sql`, que corre después del paso 04 y devuelve una fila por variable (temperatura y vibración) cuando la **mediana entre equipos del cambio porcentual** de la mediana de cada equipo, entre formato viejo y formato nuevo, queda fuera de ±0,5 %. Más el informe (no bloqueante) de los equipos con cambio individual mayor a 2 % en vibración o 1 % en temperatura. Limitación del diseño: compara dentro del mismo drop, y un drop con un solo formato no tiene "antes" y "después". Para esos meses haría falta guardar las medianas por equipo del mes anterior como línea de base.
- **Evidencia:** `docs/perfilado.md`, H-09 y su gráfico `docs/graficos/h09-trayectorias.png`; cálculo de la mediana con y sin conversión de °F (−0,008 % contra +1,24 %).

## D-16 · Sensores sospechosos: se detectan y se tratan como motivo de revisión propio
- **Contexto:** dos equipos con vibración casi cero tras un cambio de sensor: EQ-209 (de ~2,05 a 0,08 desde el 14/02; OT 40244: "Se instala VX-200, configuración de fábrica") y EQ-118 (de ~2,15 a 0,08 desde el 20/02; OT 40264, sin tipo). EQ-209 falló el 27/02 con el monitoreo en 0,08 (OT 40283: "el monitoreo no mostró nada raro"). Un tercer caso de otro tipo: la temperatura de EQ-219 queda exactamente en 65,9 °C desde el 25/02 (seis días con el mismo valor), compatible con un sensor trabado.
- **Qué decidí:** detectar el "sensor sospechoso" y tratarlo como un motivo de revisión por sí mismo ("revisar instrumentación de este equipo"), en lugar de leer una vibración baja como un equipo sano.
- **Qué descarté y por qué:** usar los valores tal como vienen (el criterio vería al equipo como sano justo antes de fallar, como pasó con EQ-209); excluir a esos equipos del criterio (se pierde justo el aviso de que el sensor no sirve).
- **Consecuencia:** un sensor ciego deja de ser un falso "sano" y pasa a ser un hallazgo accionable. **Pendientes que se cierran en el paso del criterio y se registran aquí:** (1) la regla concreta de detección (por ejemplo, caída brusca y sostenida a un nivel cercano a cero, o valor idéntico durante varios días); (2) si el valor congelado de EQ-219 entra en la misma regla; (3) cómo cabe el aviso en la lista de máximo 5 equipos (D-04): dentro de los 5 o como sección aparte.
- **Evidencia:** `docs/perfilado.md`, H-09 y H-10 (gráfico `docs/graficos/h09-trayectorias.png`). Pregunta abierta al cliente: si el sensor VX-200 se calibró y en qué escala mide.

## D-17 · OT: normalizar siempre los IDs de equipo; descartar y reportar las que sigan sin cruzar
- **Contexto:** de las 86 OT, 69 cruzan con el maestro con el ID tal cual y 17 no, por IDs sucios (`EQ103`, `eq-117`, ` EQ-101` con espacio inicial). Normalizando (recortar espacios, pasar a mayúsculas, insertar el guion) cruzan las 86: hoy no queda ningún ID huérfano.
- **Qué decidí:** dos reglas en orden. (1) Normalizar siempre el ID del equipo en las OT. (2) Si tras normalizar queda algún ID que no existe en el maestro, descartar esa OT y reportar cuántas y cuáles fueron.
- **Qué descarté y por qué:** descartar en silencio (pierde fallas sin avisar); detener el pipeline si hay huérfanos (un ID mal escrito en una OT no justifica frenar todo).
- **Consecuencia:** hoy el segundo punto no se activa (0 huérfanos); queda como regla para drops futuros. Riesgo: si la OT descartada era una falla, desaparece del backtest, por eso el reporte es obligatorio.
- **Evidencia:** `docs/perfilado.md`, H-13 (69 de 86 cruzan crudo; 86 de 86 normalizado).

## D-18 · OT: normalizar los tipos y no usar el tipo, por sí solo, para decidir qué es una falla
- **Contexto:** el campo `tipo` de las 86 OT tiene 5 valores para 3 conceptos: `PREV` (42), `Preventivo` (19), `Correctivo` (4), `CORR` (1) y vacío (20, el 23 %). El cliente avisó que "no siempre ponen el tipo".
- **Qué decidí:** mapear los sinónimos (`PREV` y `Preventivo` a preventivo; `CORR` y `Correctivo` a correctivo; vacío a "sin tipo"), con el resultado 61 preventivas, 5 correctivas y 20 sin tipo. El tipo normalizado no se usa por sí solo para decidir qué es una falla; esa regla se define aparte (H-16).
- **Qué descarté y por qué:** tratar "sin tipo" como preventivo o como correctivo: no hay base para ninguna de las dos; dejarlo como categoría propia no inventa información.
- **Consecuencia:** el tipo queda disponible como dato normalizado, pero la regla de falla se apoya también en la descripción (ver H-16). La regla de falla sigue siendo un pendiente de R3 hasta cerrar H-16.
- **Evidencia:** `docs/perfilado.md`, H-14 y H-16 (con la regla "falla = correctivo" se pierden 2 de las 5 fallas con parada y se suma 1 que no lo es).

## D-19 · Backtest: solo se evalúan los cortes con 7 días de futuro completo; la lista final se calcula igual, sin evaluación propia
- **Contexto:** el backtest califica, para cada día de corte, si un equipo de la lista falla entre 2 y 7 días después (D-08). Los datos terminan el 02/03 a las 23:45. Un corte posterior al 23/02 tiene una ventana que se pasa del final de los datos, y no se puede saber si un equipo marcado que no falló hasta el 02/03 fallará después. De las 86 OT, 25 caen en los últimos 7 días.
- **Qué decidí:** (1) el backtest usa solo los cortes del 01/02 al 23/02, los que tienen 7 días de futuro completo; (2) la lista de "esta semana" se calcula igualmente al cierre de los datos (02/03 23:45) con el mismo criterio, y el informe dice explícitamente que esa lista todavía no se puede evaluar.
- **Qué descarté y por qué:** evaluar todos los cortes hasta el último día (los cortes tardíos contarían falsas alarmas y fallas perdidas que no se pueden saber); no calcular la lista final (se pierde justo lo que pidió la jefa: qué equipos mandar esta semana).
- **Consecuencia:** el resultado del backtest es limpio pero se apoya en menos cortes (23 días). La lista final no tiene evaluación propia: su respaldo es la evidencia de los cortes anteriores. La falla de EQ-209 (27/02) sí se puede evaluar: los cortes del 20/02 al 23/02 la tienen dentro de su ventana y cuentan con futuro completo. Con solo 5 fallas el resultado es evidencia modesta (D-05).
- **Evidencia:** `docs/perfilado.md`, H-15 y H-16.

## D-20 · Qué cuenta como falla: una OT cuya descripción contiene una frase de parada o rotura, de una lista configurable
- **Contexto:** el campo `tipo` no alcanza (D-18): con la regla "falla = correctivo" se pierden 2 de las 5 fallas con parada (EQ-214 y EQ-209, con el tipo vacío) y se suma una que no lo es (EQ-120, correctivo con "sin hallazgos"). Leyendo las 86 OT hay 5 fallas con parada: EQ-107 (09/02), EQ-214 (16/02), EQ-116 (19/02), EQ-112 (22/02) y EQ-209 (27/02). EQ-206 (15/02) es una intervención correctiva con el equipo "en servicio" y queda como caso límite fuera de la regla.
- **Qué decidí:** una OT cuenta como falla si su descripción contiene alguna frase de una lista guardada en un archivo de configuración versionado (parámetro del criterio, junto con el desfase horario de D-13). El tipo no se usa para decidir. Lista inicial: `parada no programada`, `parado`, `detenido`, `fuera de servicio`, `sale de servicio`, `se para`, `disparo`, `rotura`, `dañado`, `urgencia`, `actúa protección`. Quedan afuera a propósito: `falla` (aparece en "sin falla"), `parada` suelta (aparece en "próxima parada"), `ruido` y `vibración alta`. La definición es "falla con parada". El informe mensual lista cada OT clasificada como falla con su texto, para revisión humana.
- **Qué descarté y por qué:** solo `tipo = correctivo` (pierde 2 fallas y suma 1 falsa); etiquetar a mano en un archivo (no escala al mes siguiente); una lista de frases de exclusión o detección de negaciones (complejidad para un problema que no aparece en las 86 OT; se agrega si un informe futuro muestra un falso positivo).
- **Consecuencia:** con la lista inicial el resultado de este mes es exactamente las 5 fallas, sin falsos positivos (comprobado contra las 86 OT). Las frases agregadas más allá de las 6 primeras atrapan las mismas 5 OT: dan redundancia para meses futuros, sin cambiar el resultado de hoy. **Límites declarados:** (1) una parada planificada que use una frase de la lista, por ejemplo "equipo detenido para inspección, sin falla", sería un falso positivo; (2) una falla que no detiene el equipo queda fuera de la definición; (3) con solo 5 fallas, la lista de frases está calibrada con muy poca evidencia; (4) EQ-116 fue una falla "sin aviso previo" según su OT, lo que pone en duda la asunción D-07 para ese caso.
- **Evidencia:** `docs/perfilado.md`, H-14 y H-16. Contraste: la regla con las frases específicas devuelve exactamente las 5 fallas; con la palabra suelta `parada` atraparía además a EQ-115 ("próxima parada"), y con `falla` a EQ-101 ("sin falla"). **Pregunta abierta al cliente:** si "correctivo" incluye inspecciones sin hallazgos, como la OT de EQ-120.

## D-21 · Umbral del fabricante: se usa solo como alerta de referencia ingenua en el backtest
- **Contexto:** el maestro trae un único umbral por tipo de equipo (bomba 7,1 mm/s y 85 °C; compresor 4,5 mm/s y 95 °C; turbina 2,8 mm/s y 110 °C), que no distingue entre equipos del mismo tipo: una bomba que opera normalmente en 3,2 mm/s y otra en 1,7 mm/s comparten el mismo umbral. Una alerta que dispara cuando la lectura supera ese umbral, con °F ya convertido, marca el 0,24 % de las lecturas del sistema viejo y el 0,91 % de vibración del nuevo, concentradas en pocos equipos (EQ-115, EQ-206, EQ-107, EQ-112, EQ-203). Sin convertir °F, marcaría por temperatura el 14,92 % de las lecturas del nuevo, el tipo de alerta que "avisaba todo el tiempo" y que el cliente apagó.
- **Qué decidí:** el umbral del fabricante se usa únicamente como la alerta ingenua de referencia del backtest (R6): sirve para comparar y medir cuántas falsas alarmas genera. No es el criterio propio. El criterio propio, que se apoyará en cuánto se aleja cada equipo de su propia normalidad, se diseña en el paso siguiente.
- **Qué descarté y por qué:** usar el umbral como criterio único (hereda la fatiga de alertas y no distingue entre equipos del mismo tipo); ignorarlo (sin él no hay referencia contra la cual mostrar que el criterio propio mejora).
- **Consecuencia:** el backtest compara el criterio propio contra dos referencias: elegir 5 equipos al azar y esta alerta por umbral. El criterio mínimo propuesto en SPEC R6 es superar al azar y generar menos falsas alarmas que la alerta ingenua. El diseño del criterio propio queda abierto para el paso siguiente.
- **Evidencia:** `docs/perfilado.md`, H-11 y H-12.

## D-22 · Filas ilegibles: se descartan con motivo y se cuentan, no frenan el pipeline
- **Contexto:** una lectura puede traer un timestamp o un número que no se puede leer (hoy hay 0, H-05). R4(a) las llama "inválidas descartadas".
- **Qué decidí:** descartarlas con un motivo (`ts_invalido`, `valor_no_numerico`), contarlas en la auditoría y listarlas en `salida/descartes.csv`.
- **Qué descarté y por qué:** frenar el pipeline ante cualquier fila rota: un solo dato malo bloquearía el procesamiento de todo el mes.
- **Consecuencia:** si un drop futuro trae muchas filas ilegibles, solo se nota mirando la auditoría. El test de cuadre garantiza que ninguna desaparezca sin quedar contada.
- **Evidencia:** `sql/03_lecturas_unificadas.sql`, `tests/06_cuadre.sql`; `docs/perfilado.md`, H-05.

## D-23 · Test de temperatura: rango válido de 0 a 120 °C
- **Contexto:** tras convertir °F, hace falta un control que atrape una conversión que haya fallado.
- **Qué decidí:** `tests/04_temp_c_en_rango.sql` devuelve las lecturas fuera de [0, 120] °C. El 120 queda por encima del máximo real del mes (95,8 °C) y del umbral más alto del maestro (110 °C, turbina), y por debajo del menor valor en °F sin convertir observado (126,7). El 0 es el piso físico para equipos en operación (el mínimo real es 52,6 °C).
- **Qué descarté y por qué:** techo de 150 (dejaría pasar °F sin convertir entre 126 y 150); techo de 110 (podría frenar el pipeline por una turbina recalentada real).
- **Consecuencia:** un equipo que opere a menos de 49 °C y llegue sin convertir quedaría bajo 120 y no se detectaría. Los límites de 0 y 120 son una asunción propia, a revisar con más meses.
- **Riesgo aceptado:** un valor en °F que llegue rotulado como °C (o sin convertir) de un equipo que opere por debajo de 48,9 °C (120 °F) pasa el test. Hoy no hay ninguno expuesto: el mínimo real del mes es 52,6 °C, que en °F daría 126,7 y sí se detecta, así que el margen es de 3,7 °C de temperatura de operación. Si sucede, **se pierde** exactitud en la temperatura de ese equipo: una lectura real de 45 °C entra como 113 °C, que supera el umbral de una bomba (85 °C) y genera una falsa alarma de temperatura. Eso puede ocupar uno de los 5 lugares de la lista (D-04) y ensucia el backtest sin que nada avise.
- **Cómo lo detectaríamos:** (1) el informe de equipos con cambio individual de temperatura mayor a 1 % entre sistemas (D-15) lo listaría, porque el salto sería de más de 100 %. **Todavía no está implementado:** el test de R4(c) y su informe quedan para un paso posterior, así que hoy no hay nada que lo detecte. (2) La razón de cada equipo de la lista cita su evidencia (R5), así que una temperatura imposible para ese equipo se vería al revisarla. (3) Si pasara, el siguiente control a agregar es comparar cada lectura contra la mediana de su propio equipo, en vez de contra un rango fijo para toda la flota.
- **Evidencia:** `docs/perfilado.md`, H-04 y H-12.

## D-24 · Salidas de la limpieza
- **Qué decidí:** `salida/limpieza.duckdb` más `lecturas.parquet`, `equipos.parquet`, `ot.parquet`, `auditoria.csv` y `descartes.csv`. Los tests y pasos SQL viven en `sql/` y `tests/`, con el mismo número de paso.
- **Consecuencia:** DuckDB lee parquet directo (R11); el parquet no se abre a ojo, por eso la auditoría y los descartes van en CSV.

## D-25 · Historial de corridas para observabilidad
- **Contexto:** hace falta saber qué corrió, qué falló y dónde se cortó el pipeline.
- **Qué decidí:** `salida/corridas.csv` se acumula (no se reescribe) con una fila por paso y por test en cada corrida: `id_corrida, drop_dir, orden, tipo, nombre, estado (ok|fallo|error|no_corrio), filas, duracion_s, mensaje`. Los pasos posteriores a un corte quedan como `no_corrio`.
- **Qué descarté y por qué:** construir un tablero ahora: con una corrida por mes, una tabla de 14 filas alcanza. Un tablero propio tiene sentido con corridas diarias o con 500 equipos (ver "Escalado"), y se arma sobre este CSV.
- **Consecuencia:** el historial vive en `salida/`, así que `make clean` lo borra. No avisa solo: alguien tiene que mirarlo.
- **Evidencia:** `pipeline.py`; probado con drops rotos (unidad `K` y encabezado renombrado cortan en su test; un error interno de deduplicación corta en el cuadre).

## D-26 · Backtest: toda OT reinicia el normal del equipo, con mínimo de 1 día de lecturas
- **Contexto:** la regla propia compara cada equipo contra su normal (mediana de sus 7 días anteriores). Una OT (mantenimiento, cambio de sensor) puede cambiar el nivel del equipo, así que el normal anterior deja de valer. Hay 86 OT en el mes, la mayoría preventivas.
- **Qué decidí:** el normal del día D usa solo lecturas posteriores a la última OT y anteriores a D (máximo 7 días). Nunca lecturas de D en adelante. Si entre la OT y D hay menos de 1 día, el equipo no se evalúa ese día (también si la OT cae durante D). Lo verifican `tests/backtest/normal_sin_futuro.sql` (recalcula la ventana y la mediana de todos los equipos y días con una consulta independiente) y `tests/backtest/normal_eq209.sql` (caso EQ-209: OT del 20/02 12:30; el 21/02 no se evalúa y del 22/02 al 27/02 el normal solo usa lecturas posteriores a esa OT).
- **Qué descarté y por qué:** (a) esperar 7 días completos tras cada OT: sobre los 920 equipo-días de 23 días × 40 equipos, quedan sin evaluar **419 (45,5 %)** contra **137 (14,9 %)** con 1 día (misma consulta para ambos); además EQ-209 (OT 20/02, falla 27/02) no podría anticiparse nunca. (b) Reiniciar solo tras OT de falla: un cambio de sensor en una preventiva (EQ-209, 14/02) dejaría un normal viejo y alarmas por el salto.
- **Consecuencia:** un normal de 1 día es más ruidoso que uno de 7. El backtest evalúa 783 de 920 equipo-días. **Corrección:** el plan hablaba de 41 % contra 8 %; eran dos mediciones con método distinto (la de 8 % no contaba las OT del propio día D). Las cifras de arriba salen de una sola consulta.
- **Evidencia:** `salida/backtest.duckdb` (`bt_normales`); los tests fallan al mutar la regla (usar el día D, o ignorar las OT), probado en una copia.

## D-27 · Se mantiene D-08 como métrica principal del backtest; la de 7 días es complementaria
- **Contexto:** al definir el backtest se propuso un acierto más amplio: episodio iniciado en cualquiera de los 7 días previos a una falla. Esa definición sube el número de aciertos (incluye avisos con 0 o 1 día de anticipación).
- **Qué decidí:** mantener D-08. El número principal es "fallas anticipadas con al menos 2 días", porque es lo que le sirve a la jefa para actuar. Como dato complementario se informa cuántas fallas tuvieron un episodio en los 7 días previos, aclarando que muchas no dan tiempo de actuar.
- **Qué descarté y por qué:** reemplazar D-08 por la definición de 7 días: una métrica no se cambia después de ver resultados ni porque la otra dé un número mejor.
- **Consecuencia:** el informe muestra dos conteos distintos para la misma pregunta, cada uno con su etiqueta. En este mes, con la regla principal: 2 de 5 (≥ 2 días) contra 3 de 5 (en 7 días).
- **Evidencia:** `salida/backtest.md` (los dos conteos, lado a lado); entrada en `AI-LOG.md`.

## D-28 · Backtest: reglas, episodios y combinaciones, fijados antes de ver resultados
- **Contexto:** R6 pide un backtest diario sin fuga contra una referencia ingenua (D-21).
- **Qué decidí:** (1) *Regla propia:* alerta el día D si vibración o temperatura supera k × normal durante N lecturas seguidas de 15 min dentro de D. (2) *Referencia:* alerta si una lectura del día supera el umbral del fabricante. (3) *Episodio:* días de alerta consecutivos del mismo equipo; su inicio es 00:00 del día siguiente al primer día de alerta (cuando ya se conoce). (4) *Clases:* acierto con ≥ 2 días, acierto con 0–1 día, falsa alarma (sin falla en los 7 días siguientes) o sin evaluar (los 7 días se pasan del último dato, D-19). (5) *Anti-fuga:* un loop en Python día por día; en cada vuelta las reglas solo leen vistas con `WHERE fecha < D + 1`, y `backtest.py` aborta si un archivo de reglas lee las tablas completas. (6) *Combinaciones* en `config/backtest.toml`, todas reportadas sin elegir la mejor: (1,3; 4) principal, (1,2; 4), (1,5; 4), (1,3; 8). Los primeros 7 días no se evalúan; las fallas de esos días se listan aparte (este mes: ninguna).
- **Qué descarté y por qué:** elegir la combinación después de mirar (con 5 fallas sería sobreajuste); evaluar rachas que cruzan la medianoche (más complejo, sin evidencia de que haga falta).
- **Consecuencia:** el resultado es evidencia modesta (5 fallas, cortes solapados). Falta la referencia de 5 equipos al azar (R6). El backtest corre con `make run` y sus tests se registran en `salida/corridas.csv`.
- **Evidencia:** `salida/backtest.md`: principal 2 de 5 (≥ 2 días) y 3 de 5 (en 7 días), 0 falsas alarmas; umbral del fabricante 0 de 5, 2 de 5 y 21 falsas alarmas (9,19 por semana).

## D-29 · El acierto de EQ-209 en el backtest es sólido frente al ruido, con tres límites declarados
- **Contexto:** el normal de EQ-209 el día de su alerta (23/02) es 0,087 mm/s, el nivel casi cero del sensor VX-200 instalado el 14/02 (D-16). Con un nivel tan bajo, una subida de 0,08 a ~0,12 mm/s podía ser ruido o deriva del sensor y no una degradación.
- **Qué decidí:** mirar la vibración diaria de EQ-209 antes de contar el acierto como confiable, y registrar el veredicto. Veredicto: **sólido frente al ruido**.
- **Evidencia (mediana y máximo diarios en mm/s, `salida/limpieza.duckdb`):**

| día | mediana | máximo | | día | mediana | máximo |
|---|---|---|---|---|---|---|
| 15/02 | 0,081 | 0,086 | | 22/02 | 0,094 | 0,104 |
| 16/02 | 0,081 | 0,086 | | **23/02** | **0,108** | **0,123** |
| 17/02 | 0,081 | 0,085 | | 24/02 | 0,126 | 0,140 |
| 18/02 | 0,081 | 0,087 | | 25/02 | 0,150 | 0,492 |
| 19/02 | 0,081 | 0,087 | | 26/02 | 0,178 | 0,683 |
| 20/02 | 0,082 | 0,087 | | 27/02 | 0,198 | 0,210 |
| 21/02 | 0,086 | 0,093 | | | | |

  Del 15 al 20/02 la mediana es constante (0,081) y el máximo nunca pasa de 0,087 (desvío diario 0,0021 a 0,0025). Desde el 21/02 la mediana sube todos los días sin retroceder y se multiplica por 2,3 hasta la falla (0,086 → 0,198). El mínimo del 23/02 (0,097) ya supera el máximo de todos los días de ruido (0,087). El 14/02 aparece mediana 1,981 porque el día mezcla el sensor viejo y el nuevo (cambio de sensor).
- **Límites declarados:** (1) es un solo equipo: con la regla principal se anticiparon 2 de 5 fallas (EQ-112 y EQ-209) y solo EQ-209 se revisó acá. (2) La escala del VX-200 no está validada (pregunta abierta al cliente en D-16): no sabemos si 0,2 mm/s es un valor de operación normal o de alarma para ese sensor, y 1,3 × 0,087 equivale a solo 0,03 mm/s en valor absoluto. (3) El normal sube con la propia tendencia (la ventana incluye los días de subida), lo que hace al criterio menos sensible a medida que la degradación avanza: el umbral de 1,3 × normal pasó de 0,1097 (22/02) a 0,1132 (23/02). El 21/02 no se evaluó (OT del 20/02 12:30, menos de 1 día, D-26) y el 22/02 no alertó: su máximo fue 0,104 y ninguna lectura superó 0,1097.
- **Consecuencia:** el acierto de EQ-209 se informa tal cual (anticipación 3 días), con esta nota. No cambia ninguna regla ni ningún número del backtest. La regla de sensor sospechoso (D-16) sigue pendiente.

## D-30 · Lista de cierre: episodio activo en los últimos 3 días, ordenada por desviación; sin datos aparte
- **Contexto:** R5 pide qué equipos mandar a mantenimiento al cierre de los datos (02/03 23:45) y por qué.
- **Qué decidí:** (1) *Entra* el equipo con un episodio de la regla principal (P1, D-28) cuyo último día de alerta cae en los últimos 3 días de datos (28/02 al 02/03). (2) *Orden:* por veces que su señal más desviada supera su normal, de mayor a menor: mediana de las últimas 24 h dividida por el normal del día en que esa señal empezó a alertar (el normal de antes de desviarse, no el de hoy, que ya arrastra la subida, D-29 límite 3). (3) *Razón* en palabras: señal, desde qué día, veces sobre su normal y los dos valores. (4) *Sin datos:* equipo sin ninguna lectura en las 24 h previas al cierre; va a `salida/sin-datos.csv`, no es alerta y no entra a la lista. (5) Tope de 5 (D-04): si hubiera más episodios activos, se recorta y la consola lo avisa. (6) Parámetros en `config/lista.toml`. (7) `make run` y `uv run python pipeline.py` hacen lo mismo y borran `salida/` antes (menos `corridas.csv`, D-25).
- **Qué descarté y por qué:** poner a los sin datos dentro de la lista con una marca (se confunden con alertas); comparar contra el normal de hoy (subestima una degradación que sube todos los días).
- **Consecuencia:** el resultado se recalcula con cada drop. Un test (`tests/lista/`) recalcula desde las lecturas limpias las veces sobre el normal, la ausencia de duplicados con sin datos y el orden; se comprobó que falla si se altera una cifra.
- **Evidencia:** este mes la lista tiene 1 equipo: EQ-118 (compresor), vibración a 2,44 veces su normal desde el 26/02 (0,2131 contra 0,0872 mm/s). Sin datos: EQ-110, 63 h sin lecturas (la última fue el 28/02 08:45). El umbral de 24 h se eligió porque el mayor hueco entre lecturas de los demás equipos es de 8 h 15 min.
- **Límite declarado (hallazgo):** EQ-115 no está en la lista y su vibración sigue subiendo: mediana diaria de 4,26 mm/s (15/02) a 9,36 mm/s (02/03), contra un umbral del fabricante de 7,1. Su episodio terminó el 27/02 porque el normal acompaña la subida (D-29 límite 3), y la OT preventiva del 28/02 12:45 reinició el normal (D-26): el 02/03 está a 1,09 veces su normal. La regla no lo marca y el umbral del fabricante sí. No se cambió ninguna regla; queda para decidir.
