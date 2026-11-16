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

## D-13 · Zona horaria: no corregir el desfase; dejarlo configurable y confirmar con el cliente
- **Contexto:** los timestamps no declaran zona horaria en ningún formato (todos de 19 caracteres, sin `Z` ni desfase). El ciclo diario de temperatura tiene su pico a las ~14:30 en el sistema viejo y a las ~17:30 en el nuevo: un corrimiento de unas 3 horas. Una explicación posible es que el nuevo guarde UTC y el viejo hora local (UTC−3), pero no cierra del todo: en la frontera del 10/02 al 11/02 la grilla de 15 minutos es continua, sin salto ni solape de 3 horas.
- **Qué decidí:** no corregir el dato (queda tal como llegó) y dejar el desfase como un parámetro de configuración con valor 0 por defecto. Se escribe como limitación conocida. La pregunta se envió al cliente ("¿el sistema nuevo guarda UTC o hora local?"); **la respuesta está pendiente**.
- **Qué descarté y por qué:** restar 3 horas a todo el sistema nuevo: se basa en una hipótesis que no cierra en la frontera, y si está equivocada corrompe el dato (viola "no inventa señales", R4). Decidir sin preguntar: sale barato preguntar.
- **Consecuencia:** el criterio trabaja con cortes y métricas diarias, así que 3 horas casi no cambian el resultado. Cualquier análisis por hora del día quedaría torcido hasta tener la respuesta. Cuando el cliente responda, se corrige cambiando una línea de configuración.
- **Evidencia:** `docs/perfilado.md`, H-07 y su gráfico `docs/graficos/h07-ciclo-diario.png`. **Pendiente:** respuesta del cliente; actualizar esta decisión cuando llegue.

## D-14 · Huecos de lecturas: no imputar y avisar cuando un equipo se queda sin telemetría
- **Contexto:** faltan 220 lecturas de las 115.200 esperadas (40 equipos × 2.880). Hay dos patrones: EQ-110 deja de reportar el 28/02 a las 08:45 y no vuelve (252 faltantes, sin OT que lo explique); y cinco equipos (EQ-107, 112, 116, 209, 214) tienen un único hueco de 8 h 15 min (32 lecturas) el mismo día de su falla con parada según las OT. La ausencia de lecturas coincide con equipos parados, así que es información y no ruido.
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
- **Evidencia:** `docs/perfilado.md`, H-09 y su gráfico `docs/graficos/h09-trayectorias.png`; cálculo de la mediana con y sin conversión de °F (−0,008 % contra +1,24 %).
