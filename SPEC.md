# SPEC — Priorización de mantenimiento de 40 equipos rotativos

## Objetivo
1. Decir qué equipos mandar a mantenimiento al cierre de los datos (máximo 5), con la razón de cada uno.
2. Demostrar con un backtest diario, sin fuga de información, que el criterio habría anticipado las fallas del mes sin llenar de falsas alarmas.
3. Entregarlo con un comando, un dashboard para la jefa y skills para que otra persona procese el mes siguiente.

**Cómo leer los requisitos:** cada uno dice *por qué importa* y *cómo se comprueba*. Etiquetas: **[AUTO]** lo verifica un test automático dentro de `make run`; `make test` repite una parte sin regenerar (qué cubre cada uno: R1 y D-36); **[MANUAL]** lo revisa una persona, no hay test; **[PENDIENTE]** se define tras mirar los datos (hoy no queda ninguno abierto, D-39); **[FUERA DE ALCANCE]** no se entrega, con su motivo. El SPEC se escribió antes de ver los datos y se reconcilió con lo que el pipeline hace (D-38).

## Requisitos

**R1. Un comando corre todo, offline y con resultado repetible**
- *Por qué importa:* el enunciado exige un solo comando. Y si dos corridas dan listas distintas, nadie puede confiar en la lista.
- *Se comprueba:* **[AUTO]** `make run` termina con código 0 y se corta con código distinto de 0 si algún test falla. **[MANUAL]** en un clon limpio (`git clone` + `uv sync` + `make run`) termina con código 0 y existen los archivos de salida; `grep -rEn "requests|urllib|httpx|anthropic|openai|socket" *.py sql/ tests/ config/` sale vacío (no hay carpeta `src/`); dos corridas seguidas dan el mismo `shasum` en `salida/lista.csv`.
- *Qué verifica cada comando (D-36):* `make run` corre todos los tests (limpieza, backtest, lista y R8) y se corta con código distinto de 0 si alguno falla (los tests SQL, si devuelven filas; `r8.py`, con código 1). `make test` vuelve a correr, sobre lo ya generado y sin regenerar nada, los 8 tests de limpieza y el chequeo R8; no cubre los de backtest ni los de lista. Si falta `salida/`, falla y pide correr `make run` primero.

**R2. `drop/` no se modifica**
- *Por qué importa:* son los datos crudos del cliente; si cambian, toda la evidencia pierde valor.
- *Se comprueba:* **[MANUAL]** `git diff --exit-code 81956cb HEAD -- drop/` (81956cb es el commit que lo incorporó) y `git status --porcelain drop/` vacío tras `make run`. No hay test; lo protegen el deny de `.claude/settings.json` y `chmod -R a-w drop/` (D-03).

**R3. Perfilado de los datos**
- *Por qué importa:* no hay diccionario de datos; todas las decisiones siguientes dependen de lo que descubramos acá.
- *Se comprueba:* **[AUTO]** `salida/auditoria.csv` lo genera el pipeline y cuenta, por fuente y motivo, lo que entra, sale y queda (lo comprueba `tests/06_cuadre.sql`). **[MANUAL]** `docs/perfilado.md` está hecho con consultas SQL que están en el propio documento; `docs/herramientas/perfilado.py insertar` pega sus salidas y el pipeline no lo regenera. Trae cifras: archivos por formato y fecha del cambio, duplicados, nulos por columna, OT sin tipo, regla de falla y cantidad de fallas resultante. Contrastable con el dato: `ls drop/lecturas-*.csv | wc -l` da 30 y coincide con lo informado.
- **[CERRADO en D-20]** falla = OT cuya descripción contiene una frase de parada o rotura de `config/frases-falla.txt`; el tipo no se usa. Ejemplos: "Disparo… equipo detenido" (sin tipo) es falla; "Revisión de cableado. Sin falla." no lo es.

**R4. Ingesta que unifica formatos y no inventa señales**
- *Por qué importa:* si el sistema nuevo cambió de unidad o de zona horaria, no hay error, pero salen falsas alarmas masivas.
- *Se comprueba:* **[AUTO]** (a) filas crudas = limpias + duplicados descartados + inválidas descartadas (`tests/06_cuadre.sql`); (b) 0 duplicados por (equipo, timestamp) (`tests/04_sin_duplicados.sql`). **No automatizado:** (c) la mediana de cada variable por equipo antes y después del 11/02 queda dentro de una tolerancia.
- **[CERRADO en D-15]** la tolerancia de (c) es ±0,5 % sobre la mediana de los cambios entre equipos. El test no está implementado (riesgo aceptado en D-15).

**R5. Lista semanal de ≤5 equipos con razón verificable**
- *Por qué importa:* es la respuesta a la pregunta de la jefa. Una razón que no se puede comprobar no sirve para creerle.
- *Se comprueba:* **[AUTO]** `salida/lista.csv` tiene ≤5 filas y las columnas `puesto, equipo, tipo, planta, senal, desde, veces_sobre_normal, valor_actual, normal, razon`. El corte es el último timestamp de los datos. `tests/lista/01_lista_coherente.sql` recalcula, desde las lecturas limpias (no las crudas), la evidencia citada de cada equipo y verifica que coincida. Salidas relacionadas (D-30, D-31): `salida/sobre-umbral.csv` (regla SU, sección aparte, comprobada por `tests/lista/02_sobre_umbral_coherente.sql`) y `salida/sin-datos.csv` (equipos sin lecturas en las últimas 24 h; no son alertas).

**R6. Backtest diario sin fuga, comparado contra referencias**
- *Por qué importa:* es la razón para creerle a la lista. Un resultado sin referencia no dice si es bueno, y una fuga lo vuelve falso.
- *Se comprueba:* **[AUTO]**
  - *Anti-fuga (D-28):* en cada corte las reglas solo leen vistas con `WHERE fecha < D + 1` y `backtest.py` aborta si un archivo de reglas lee las tablas completas; `tests/backtest/normal_sin_futuro.sql` recalcula el normal con una consulta independiente. No hay un test que compare la lista con y sin los datos posteriores al corte.
  - *Acierto:* falla de OT entre 2 y 7 días después del corte.
  - *Referencias:* una alerta ingenua por umbral del fabricante (FAB), que imita al sistema que apagaron, y la regla complementaria SU (D-31). La referencia de 5 equipos al azar queda fuera de alcance (D-37). Resultados en `salida/backtest.md`, `backtest.csv`, `backtest-fallas.csv` y `backtest-episodios.csv`.
  - *Fatiga:* se mide equipos marcados y falsas alarmas por semana en las tres.
  - *Criterio mínimo (propuesta a confirmar):* superar al azar y generar menos falsas alarmas que la alerta ingenua.
- **[CERRADO en D-39]** no se fija una meta numérica de precisión y recall. El criterio mínimo que sí se evalúa es generar menos falsas alarmas que la alerta ingenua.
- *Limitación declarada:* con un mes de datos no hay un tramo reservado para validar de verdad. Los parámetros van en un archivo versionado y la limitación va escrita en el README.

**R7. Ventana de anticipación (intervalo P-F) estimada con datos [FUERA DE ALCANCE, D-37]**
- *Por qué importa:* dice cuánto tiempo hay para actuar. Si es de horas, una lista semanal no sirve para esas fallas.
- *Se comprueba:* **[AUTO]** `salida/ventana-pf.csv` (no se genera: fuera de alcance) con una fila por falla (equipo, fecha de la OT, primer día con señal anormal, días de diferencia). El rango del informe sale de esa tabla. Si hay menos de 3 fallas con señal (umbral propuesto), el informe dice "no estimable" en vez de dar un número.

**R8. Dashboard para la jefa**
- *Por qué importa:* una jefa de mantenimiento no lee CSV; tiene que entender la lista en un minuto.
- *Se comprueba:* **[AUTO]** (`tests/dashboard/r8.py`) `salida/dashboard.html` es autocontenido: ninguna etiqueta descarga un recurso de la red (`<script src="http`, `<link href="http`, `src="http` en imágenes o iframes) ni lo hace el CSS (`url(http`, `@import`). Los enlaces de texto dentro de plotly.js embebido no cuentan: no descargan nada (D-34). Contiene cada equipo de la lista, y su precisión y recall son idénticos a `backtest.csv`. El recall es una columna de `backtest.csv`; la precisión no tiene columna y se deriva de sus conteos: avisos acertados sobre avisos ya juzgables, donde acierto = falla dentro de los 7 días, incluso el mismo día (definición en D-34, complementaria a D-08 y D-27).
- **[MANUAL]** se responden "¿qué equipos?", "¿por qué?" y "¿puedo creerle?" en menos de un minuto.

**R9. Documentación de entrega**
- *Por qué importa:* el evaluador valora el razonamiento y cómo se verificó, no solo el código.
- *Se comprueba:* **[MANUAL]** los comandos del README, copiados y pegados en un clon limpio, funcionan. `DECISIONES.md` tiene la sección "Escalado" con el cálculo: 500 equipos × 1.440 lecturas/día = 720.000/día, contra 40 × 96 = 3.840 hoy (×187,5). La sección la escribe el autor y hoy tiene solo los títulos. `AI-LOG.md` tiene al menos una entrada.

**R10. Dos skills (`leer-lecturas` y `normalizar-ot`); el procesamiento completo es `make run DROP=<carpeta>`**
- *Por qué importa:* es la prueba del enunciado: con el drop del mes que viene, otra persona lo procesa con un agente usando solo las skills.
- *Se comprueba:* **[AUTO]** el pipeline acepta `DROP_DIR=<ruta>` (`make run DROP=<carpeta>`), que corre limpieza, backtest, lista y dashboard. **[MANUAL]** cada `SKILL.md` en `.claude/skills/` tiene `name` y `description` válidos (no hay test). Las skills cubren la limpieza de lecturas y de OT; el resto lo hace ese mismo comando.
- **[MANUAL]** un agente nuevo, sin el contexto de esta conversación, con solo las skills y un drop de prueba, procesa el drop sin ayuda. Se registra en AI-LOG (hecho para las dos skills).
- **[CERRADO en D-39]** drop de prueba: `tests/fixtures/` (los dos formatos de lecturas ya conocidos y 5 OT inventadas) y `tests/fixtures-trampa/` (7 OT con un equipo fuera del maestro y un tipo desconocido). **Ninguno prueba un formato de lecturas nuevo:** usan los mismos dos encabezados del drop real.

**R11. (Opcional) Salida lista para sumar un agente analista [FUERA DE ALCANCE, D-38]**
- *Por qué importa:* deja abierta la "milla extra" sin comprometer lo obligatorio.
- *Se comprobaría:* `salida/DICCIONARIO.md` describe todas las columnas de cada archivo de salida (un test compara ambas cosas), y DuckDB consulta cada archivo sin error. No existe `DICCIONARIO.md` ni su test. El agente en sí no es obligatorio.

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
- Agente analista y R11 (`DICCIONARIO.md` con su test): no existen; no hay nada preparado. Lo obligatorio va primero (D-38).
- Modelo de machine learning: con pocas fallas sobreajusta y no explica sus decisiones (D-06).
- Datos en tiempo real, alertas push y despliegue en cloud: van en la sección de escalado.
- Referencia de 5 equipos al azar (parte de R6): el resultado depende de cómo se defina "azar" y con 5 fallas es muy variable; haría falta fijar definición y semilla antes de correr (D-37).
- Ventana P-F (R7): por prioridad y tiempo, lo obligatorio va primero; no es inviable, 4 de las 5 fallas muestran señal previa y quedó sin formalizar (D-37).

## Verificación final
1. Lo que se verifica hoy:
   - `make run` regenera `salida/` y corre todos los tests (limpieza, backtest, lista y R8). Termina con código 0 o se corta con código distinto de 0.
   - `make test` repite, sobre el `salida/` ya generado, los 8 tests de limpieza y el chequeo R8; no cubre los de backtest ni los de lista (D-36). En verde sobre un `salida/` viejo dice que ese `salida/` es coherente, no que el código actual lo sea.
   - Clon limpio (`git clone` + `uv sync` + `make run` + `make test`): a mano.
2. No automatizado hoy: R1 (clon limpio, `shasum` de dos corridas, `grep` sin red), R2 (`git diff` de `drop/`), R3 (`docs/perfilado.md` es manual), R4(c), R9 (comandos del README en un clon limpio y la sección Escalado), R10 (formato de `SKILL.md` y prueba con un agente nuevo) y R11 (fuera de alcance, D-38). Faltan también R7 y la referencia al azar de R6 (D-37).
3. Revisión manual del dashboard con las 3 preguntas (R8).
4. Prueba de un agente nuevo con solo las skills sobre un drop de prueba, registrada en AI-LOG (R10).
5. Todo ítem [PENDIENTE] tiene su valor cerrado y registrado en `DECISIONES.md` (D-39).
