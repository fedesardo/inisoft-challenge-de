# SPEC — Priorización de mantenimiento de 40 equipos rotativos

## Objetivo
1. Decir qué equipos mandar a mantenimiento al cierre de los datos (máximo 5), con la razón de cada uno.
2. Demostrar con un backtest diario, sin fuga de información, que el criterio habría anticipado las fallas del mes sin llenar de falsas alarmas.
3. Entregarlo con un comando, un dashboard para la jefa y skills para que otra persona procese el mes siguiente.

**Cómo leer los requisitos:** cada uno dice *por qué importa* y *cómo se comprueba*. Etiquetas: **[AUTO]** lo verifica un test automático: todos corren dentro de `make run`, y `make test` repite una parte sin regenerar (qué cubre cada uno: R1 y D-36); **[MANUAL]** lo revisa una persona; **[PENDIENTE]** se define tras mirar los datos (PENDIENTE TRAS PERFILADO).

## Requisitos

**R1. Un comando corre todo, offline y con resultado repetible**
- *Por qué importa:* el enunciado exige un solo comando. Y si dos corridas dan listas distintas, nadie puede confiar en la lista.
- *Se comprueba:* **[AUTO]** en un clon limpio (`git clone` + `uv sync` + `make run`) termina con código 0 y existen todos los archivos de salida. `grep -rEn "requests|urllib|httpx|anthropic|openai|socket" src/` sale vacío. Dos corridas seguidas dan el mismo `shasum` en `lista-semanal.csv`.
- *Qué verifica cada comando (D-36):* `make run` corre todos los tests (limpieza, backtest, lista y R8) y se corta con código distinto de 0 si alguno falla (los tests SQL, si devuelven filas; `r8.py`, con código 1). `make test` vuelve a correr, sobre lo ya generado y sin regenerar nada, los 8 tests de limpieza y el chequeo R8; no cubre los de backtest ni los de lista. Si falta `salida/`, falla y pide correr `make run` primero.

**R2. `drop/` no se modifica**
- *Por qué importa:* son los datos crudos del cliente; si cambian, toda la evidencia pierde valor.
- *Se comprueba:* **[AUTO]** `git diff --exit-code 81956cb HEAD -- drop/` (81956cb es el commit que lo incorporó) y `git status --porcelain drop/` vacío tras `make run`.

**R3. Perfilado de los datos, generado por el pipeline**
- *Por qué importa:* no hay diccionario de datos; todas las decisiones siguientes dependen de lo que descubramos acá.
- *Se comprueba:* **[AUTO]** `salida/perfilado.md` se genera con consultas SQL y trae cifras: archivos por formato y fecha del cambio, duplicados descartados, nulos por columna, OT sin tipo, regla de falla y cantidad de fallas resultante. Contrastable con el dato: `ls drop/lecturas-*.csv | wc -l` da 30 y coincide con lo informado.
- **[CERRADO en D-20]** falla = OT cuya descripción contiene una frase de parada o rotura de `config/frases-falla.txt`; el tipo no se usa. Ejemplos: "Disparo… equipo detenido" (sin tipo) es falla; "Revisión de cableado. Sin falla." no lo es.

**R4. Ingesta que unifica formatos y no inventa señales**
- *Por qué importa:* si el sistema nuevo cambió de unidad o de zona horaria, no hay error, pero salen falsas alarmas masivas.
- *Se comprueba:* **[AUTO]** (a) filas crudas = limpias + duplicados descartados + inválidas descartadas; (b) 0 duplicados por (equipo, timestamp); (c) la mediana de cada variable por equipo antes y después del 11/02 queda dentro de una tolerancia.
- **[PENDIENTE]** la tolerancia de (c).

**R5. Lista semanal de ≤5 equipos con razón verificable**
- *Por qué importa:* es la respuesta a la pregunta de la jefa. Una razón que no se puede comprobar no sirve para creerle.
- *Se comprueba:* **[AUTO]** `salida/lista-semanal.csv` tiene ≤5 filas y las columnas `equipo, puntaje, razon`. El corte es el último timestamp de los datos. Un test recalcula, con una consulta independiente sobre las lecturas crudas, la evidencia citada en `razon` de cada equipo y verifica que coincida.

**R6. Backtest diario sin fuga, comparado contra referencias**
- *Por qué importa:* es la razón para creerle a la lista. Un resultado sin referencia no dice si es bueno, y una fuga lo vuelve falso.
- *Se comprueba:* **[AUTO]**
  - *Anti-fuga:* para cada corte, la lista calculada con todos los datos es idéntica a la calculada con los datos recortados a antes del corte.
  - *Acierto:* falla de OT entre 2 y 7 días después del corte.
  - *Referencias:* 5 equipos al azar y una alerta ingenua por umbral del fabricante, que imita al sistema que apagaron.
  - *Fatiga:* se mide equipos marcados y falsas alarmas por semana en las tres.
  - *Criterio mínimo (propuesta a confirmar):* superar al azar y generar menos falsas alarmas que la alerta ingenua.
- **[PENDIENTE]** la meta numérica de precisión y recall.
- *Limitación declarada:* con un mes de datos no hay un tramo reservado para validar de verdad. Los parámetros van en un archivo versionado y la limitación va escrita en el README.

**R7. Ventana de anticipación (intervalo P-F) estimada con datos**
- *Por qué importa:* dice cuánto tiempo hay para actuar. Si es de horas, una lista semanal no sirve para esas fallas.
- *Se comprueba:* **[AUTO]** `salida/ventana-pf.csv` con una fila por falla (equipo, fecha de la OT, primer día con señal anormal, días de diferencia). El rango del informe sale de esa tabla. Si hay menos de 3 fallas con señal (umbral propuesto), el informe dice "no estimable" en vez de dar un número.

**R8. Dashboard para la jefa**
- *Por qué importa:* una jefa de mantenimiento no lee CSV; tiene que entender la lista en un minuto.
- *Se comprueba:* **[AUTO]** (`tests/dashboard/r8.py`) `salida/dashboard.html` es autocontenido: ninguna etiqueta descarga un recurso de la red (`<script src="http`, `<link href="http`, `src="http` en imágenes o iframes) ni lo hace el CSS (`url(http`, `@import`). Los enlaces de texto dentro de plotly.js embebido no cuentan: no descargan nada (D-34). Contiene cada equipo de la lista, y su precisión y recall son idénticos a `backtest.csv`. El recall es una columna de `backtest.csv`; la precisión no tiene columna y se deriva de sus conteos: avisos acertados sobre avisos ya juzgables, donde acierto = falla dentro de los 7 días, incluso el mismo día (definición en D-34, complementaria a D-08 y D-27).
- **[MANUAL]** se responden "¿qué equipos?", "¿por qué?" y "¿puedo creerle?" en menos de un minuto.

**R9. Documentación de entrega**
- *Por qué importa:* el evaluador valora el razonamiento y cómo se verificó, no solo el código.
- *Se comprueba:* **[AUTO]** los comandos del README, copiados y pegados en un clon limpio, funcionan. `DECISIONES.md` tiene la sección "Escalado" con el cálculo: 500 equipos × 1.440 lecturas/día = 720.000/día, contra 40 × 96 = 3.840 hoy (×187,5). `AI-LOG.md` tiene al menos una entrada.

**R10. Dos skills: leer un drop y procesar un drop completo**
- *Por qué importa:* es la prueba del enunciado: con el drop del mes que viene, otra persona lo procesa con un agente usando solo las skills.
- *Se comprueba:* **[AUTO]** cada `SKILL.md` en `.claude/skills/` tiene `name` y `description` válidos, y el pipeline acepta `DROP_DIR=<ruta>`.
- **[MANUAL]** un agente nuevo, sin el contexto de esta conversación, con solo las skills y un drop de prueba, produce los archivos de R5 y R6 sin ayuda. Se registra en AI-LOG.
- **[PENDIENTE]** diseño del drop de prueba. Si se arma copiando el drop con fechas corridas, no prueba un formato nuevo, y hay que decirlo.

**R11. (Opcional) Salida lista para sumar un agente analista**
- *Por qué importa:* deja abierta la "milla extra" sin comprometer lo obligatorio.
- *Se comprueba:* **[AUTO]** `salida/DICCIONARIO.md` describe todas las columnas de cada archivo de salida (un test compara ambas cosas), y DuckDB consulta cada archivo sin error. El agente en sí no es obligatorio.

## Restricciones
- Python 3.12 con uv; DuckDB con SQL para todo el procesamiento; pandas y plotly solo de apoyo y para el dashboard.
- Sin LLM ni servicios externos al correr el pipeline, y sin cuentas cloud ni servicios pagos. `uv sync` necesita internet una sola vez, para bajar las librerías.
- `drop/` es de solo lectura; todo lo derivado va a `salida/`.
- Lista de máximo 5 equipos (D-04).
- Un paso, un commit. Errores de la IA en `AI-LOG.md`, decisiones con su evidencia en `DECISIONES.md`.

## Asunciones
- Las OT son la fuente de verdad de las fallas, aunque falte el tipo (a verificar en R3).
- Antes de cada falla hay señal detectable en vibración o temperatura (D-07).
- Los duplicados vienen solo del sistema viejo, como dice el cliente (a verificar en R4).
- Un acierto exige al menos 2 días de anticipación, a confirmar con el cliente (D-08).
- "Esta semana" son los 7 días posteriores al último dato, a confirmar con el cliente (D-33).
- Con pocas fallas, el backtest es evidencia modesta y los cortes diarios se solapan (D-05).

## Fuera de alcance
- Agente analista: queda preparado (R11) y no se entrega. Lo obligatorio va primero.
- Modelo de machine learning: con pocas fallas sobreajusta y no explica sus decisiones (D-06).
- Datos en tiempo real, alertas push y despliegue en cloud: van en la sección de escalado.

## Verificación final
1. `make run && make test` en un clon limpio pasa (R1 a R9, R11). El que verifica todo es `make run`; `make test` solo repite los tests de limpieza y R8 sobre lo generado (D-36).
2. Revisión manual del dashboard con las 3 preguntas (R8).
3. Prueba de un agente nuevo con solo las skills sobre un drop de prueba, registrada en AI-LOG (R10).
4. Todo ítem [PENDIENTE] tiene su valor cerrado y registrado en `DECISIONES.md`.
