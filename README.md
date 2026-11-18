# Challenge Data Engineering

## Qué hace

Un cliente de energía manda un mes de telemetría (vibración y temperatura cada 15 minutos) de sus equipos rotativos, el maestro de equipos con los umbrales del fabricante y las órdenes de trabajo (OT). La jefa de mantenimiento pide saber a cuáles equipos mandar a mantenimiento esta semana y alguna razón para creerle a la lista. El año pasado apagaron un sistema de alertas porque avisaba todo el tiempo.

Este proyecto limpia los datos, decide qué equipos marcar, mide con un backtest si ese criterio habría anticipado las fallas del mes sin llenar de falsas alarmas, y lo presenta en un dashboard. Todo con un comando, sin red y sin ningún modelo de lenguaje.

"Esta semana" son los 7 días posteriores al último dato (D-33, asunción a confirmar con el cliente). La lista es una foto al cierre de los datos, no una predicción para esa semana.

## Aviso: datos del cliente

`drop/` son los datos crudos del cliente y están versionados para que `make run` funcione en un clon limpio (D-01). El repo es privado y no se puede publicar tal cual. `drop/` es de solo lectura: nada del proyecto lo modifica.

## Requisitos

- [uv](https://docs.astral.sh/uv/). Una sola vez, `uv sync` baja Python 3.12 y las librerías (DuckDB, pandas, plotly); esa es la única vez que hace falta internet.
- `make` es opcional: cada comando tiene su equivalente con `uv run`.
- Se desarrolló en macOS; no se probó en otros sistemas.

## Cómo correrlo

```
make run                      # con make
uv run python pipeline.py     # sin make
```

Regenera todo `salida/` desde cero: limpieza (pasos SQL y sus tests), backtest, lista de cierre y dashboard. Solo se conserva `salida/corridas.csv`, el historial de corridas.

- **Si todo sale bien**, termina con código 0 y la consola muestra la auditoría de filas y no hay ningún `TEST FALLÓ` ni `ERROR`.
- **Si un test devuelve filas**, la consola muestra `TEST FALLÓ` con las filas que rompen la regla, el pipeline se corta con código 1 y los pasos que no corrieron quedan como `no_corrio` en `salida/corridas.csv`. Un formato de archivo o una unidad de temperatura desconocidos se cortan así.
- `make clean` borra `salida/` entera, incluido `corridas.csv`.

## Procesar un drop nuevo

Un drop es una carpeta con `lecturas-*.csv`, `equipos.csv` y `ordenes-de-trabajo.csv`.

```
make run DROP=ruta/al/drop                            # con make
DROP_DIR=ruta/al/drop uv run python pipeline.py       # sin make
```

**`make run DROP=otra/carpeta` borra `salida/`** (menos `corridas.csv`). Antes de procesar el mes nuevo, copiá lo del mes anterior fuera del repo, por ejemplo `cp -R salida ../salida-mes-anterior`.

Hay dos skills en `.claude/skills/` para que un agente de IA procese el drop sin conocer el proyecto:

- `leer-lecturas`: lee y unifica los `lecturas-*.csv` de los dos formatos de captura. Se activa al recibir un drop nuevo o ante un encabezado raro. Ante un formato desconocido no lo adivina: frena y pregunta.
- `normalizar-ot`: normaliza `ordenes-de-trabajo.csv` y marca qué OT son fallas según `config/frases-falla.txt`. Avisa de cada OT descartada.

Las skills cubren la limpieza de lecturas y de OT. El procesamiento completo (limpieza, backtest, lista y dashboard) es el mismo `make run DROP=<carpeta>`. Un drop de prueba, con datos inventados, está en `tests/fixtures/` y `tests/fixtures-trampa/`; usan los mismos dos formatos de lecturas del drop real, así que no prueban un formato nuevo.

Después de procesar, mirar `salida/lista.csv`, `sobre-umbral.csv`, `sin-datos.csv`, `backtest.md` y `dashboard.html`. `config/notas-equipo.toml` tiene notas de presentación atadas a equipos de este mes; el dashboard las muestra solo si ese equipo aparece en alguna lista.

## Tests

```
make test                               # con make
uv run python tests/correr.py           # sin make
```

`make test` vuelve a correr tests sobre lo que ya está en `salida/`, sin regenerar ni escribir nada. Si `salida/` no existe, falla y pide correr `make run` primero. En un clon limpio `salida/` no existe: está fuera del repo.

- **Cubre:** los tests de limpieza (`tests/NN_*.sql`) y el chequeo R8 del dashboard (`tests/dashboard/r8.py`): que no descargue recursos de la red, que contenga cada equipo de la lista y que su recall y su precisión coincidan con `backtest.csv` y `backtest-episodios.csv`.
- **No cubre:** los tests de backtest (`tests/backtest/`) y de lista (`tests/lista/`). Corren solo dentro de `make run`, que se corta con código distinto de 0 si alguno devuelve filas. Para verificar todo, el comando es `make run` (D-36).
- **Un `make test` en verde sobre un `salida/` viejo** dice que ese `salida/` es coherente, no que el código actual lo sea.
- **Límite del chequeo R8:** no ve un script propio que descargue algo al ejecutarse; la prueba final es abrir `salida/dashboard.html` sin internet (D-34).

## Qué produce `salida/`

- `lista.csv`: equipos con un episodio de alerta activo en los últimos días de datos, del que más se aparta de su normal al que menos, cada uno con su razón en palabras simples. Es la regla propia, **P1**. El tope de equipos y la ventana de "últimos días" están en `config/lista.toml`.
- `sobre-umbral.csv`: sección aparte, regla complementaria **SU**: equipos con la mediana diaria de vibración sobre el umbral del fabricante varios días seguidos, activa en los últimos días de datos, con su razón. Se agregó después de ver el caso EQ-115 (D-31).
- `sin-datos.csv`: equipos sin lecturas en las horas previas al cierre (el límite está en `config/lista.toml`). No son alertas: no hay con qué evaluarlos.
- `dashboard.html`: para la jefa de mantenimiento. Una frase con la respuesta y la semana a la que aplica, una franja de números con el mapa de la flota, una tarjeta por equipo (acción, por qué, qué cambió, qué tan confiable), la prueba del aviso contra el umbral del fabricante con las fallas una por una, y el detalle plegable por equipo con su gráfico. Abre sin internet; las cifras salen de los CSV de esta carpeta y de `limpieza.duckdb`.
- `backtest.md`, `backtest.csv`, `backtest-fallas.csv`, `backtest-episodios.csv`, `backtest.duckdb`: la evidencia de que el criterio es confiable. La regla del umbral del fabricante en una lectura es **FAB**, la alerta ingenua de referencia.
- `corridas.csv`, `auditoria.csv`, `descartes.csv`, `limpieza.duckdb`, `*.parquet`: bitácora y datos limpios. Todo se consulta con DuckDB. No hay un diccionario de columnas (R11 quedó fuera de alcance, D-38): los encabezados de cada CSV son el nombre de cada columna.

## Cómo decide y cómo se mide

- **Normal:** la mediana de lo que el equipo midió en los días anteriores (la ventana está en `config/backtest.toml`), solo con lecturas posteriores a su última OT, porque un mantenimiento o un cambio de sensor puede cambiar su nivel (D-26).
- **Alerta del día:** vibración o temperatura sobre 1,30 × el normal durante 4 lecturas seguidas (P1, `config/backtest.toml`).
- **Episodio:** días de alerta consecutivos del mismo equipo.
- **Falla:** OT cuya descripción contiene una frase de parada o rotura de `config/frases-falla.txt`; el tipo de OT no se usa (D-20).
- **Backtest:** una lista por cada día de corte, usando solo datos anteriores al corte. Un aviso cuenta como acierto si el equipo falla entre 2 y 7 días después (D-08). Se compara contra FAB y SU, y se reporta cuántas falsas alarmas genera cada una. Los parámetros se fijaron antes de ver resultados y las combinaciones alternativas se reportan todas (D-28).

## Resultado de este mes

Son resultados del drop de febrero (`drop/`), tomados de `salida/backtest.md`, `lista.csv`, `sobre-umbral.csv` y `sin-datos.csv`. Si se procesa otro drop, estos números cambian.

- **Fallas anticipadas:** P1 anticipó con al menos 2 días 2 de las 5 fallas del mes (EQ-112 y EQ-209); 3 de 5 tuvieron un episodio en los 7 días previos. El umbral del fabricante anticipó 0 de 5.
- **Falsas alarmas** en los 16 días con 7 días de futuro completo: P1 0; el umbral del fabricante 21 (9,19 por semana).
- **Lista de cierre:** `lista.csv` tiene a EQ-118, `sobre-umbral.csv` a EQ-115 y `sin-datos.csv` a EQ-110.

Con 5 fallas es evidencia modesta (ver Limitaciones). La lista de cierre no tiene evaluación propia: sus últimos días no tienen 7 días de futuro (D-19).

## Estructura de carpetas

```
pipeline.py      un solo comando: limpieza, backtest, lista y dashboard
backtest.py      backtest diario sin fuga
lista.py         lista de cierre, sobre-umbral y sin datos
dashboard.py     genera salida/dashboard.html
Makefile         run, test, clean
sql/             pasos de limpieza 01 a 07; sql/backtest/ y sql/lista/ con las reglas
tests/           tests de limpieza (NN_*.sql), de backtest, de lista y del dashboard;
                 fixtures/ y fixtures-trampa/ son drops de prueba con datos inventados
config/          parámetros: backtest.toml, lista.toml, notas-equipo.toml, frases-falla.txt
drop/            datos crudos del cliente, solo lectura
salida/          todo lo generado (fuera del repo, se regenera con make run)
docs/            perfilado.md (hallazgos de los datos), conceptos.md, herramientas/, planes/
.claude/skills/  las dos skills para procesar un drop
.claude/settings.json      permisos del agente de IA en este repo (D-03)
.claude/agents/revisor.md  agente de solo lectura que revisó el repo contra SPEC.md; es una
                           herramienta de proceso, NO el agente analista opcional del enunciado
                           (ese quedó fuera de alcance)
CLAUDE.md        instrucciones del proyecto para el agente de IA
pyproject.toml, uv.lock, .python-version   dependencias y versión de Python para uv
docs/graficos/   gráficos del perfilado y el script que los genera
```

## Limitaciones

- **Un mes y 5 fallas:** evidencia modesta. Los cortes diarios se solapan y no hay un tramo reservado para validar (D-05, SPEC R6).
- **SU no está validada:** se definió después de ver el caso EQ-115 y anticipó 0 de 5 fallas (D-31).
- **Un solo antecedente del sensor VX-200 (EQ-209):** la escala de ese sensor no está validada, y EQ-118, el único equipo de la lista de este mes, lo usa (D-29, D-32).
- **Zona horaria del sistema nuevo sin confirmar:** el dato no se corrige. Corregirla requiere código (D-13).
- **Regla de sensor sospechoso sin construir** (D-16), y sin test de nivel estable entre sistemas (R4(c), riesgo aceptado en D-15).
- **Falla = frase en la descripción de la OT:** una parada planificada con esas palabras sería un falso positivo, y una falla que no detiene el equipo queda afuera (D-20).
- **"Esta semana"** es una asunción a confirmar con el cliente (D-33).
- **Fuera de alcance:** el agente analista y el diccionario de columnas (R11), un modelo de machine learning, datos en tiempo real con alertas push y despliegue en cloud, la referencia de 5 equipos al azar, la ventana de anticipación P-F, la regla de sensor sospechoso, el test de nivel estable entre sistemas (R4(c)), el test de equivalencia anti-fuga, el parámetro configurable de zona horaria, el perfilado generado por el pipeline (R3) y la prueba de las skills con un formato de lecturas nuevo. Los motivos están en `DECISIONES.md`.
- **Las skills no se probaron con un formato de lecturas nuevo:** los drops de prueba usan los dos formatos conocidos.
- **`make test` no verifica backtest ni lista.**
- **El "0 contra 21" se mide sobre días distintos:** P1 no evalúa a un equipo el día de cada OT ni el siguiente (D-26), y el umbral del fabricante sí. Dos de sus 21 falsas alarmas caen en días que P1 no podía evaluar (D-40).

## Dónde seguir

- `SPEC.md`: qué se prometió y cómo se comprueba cada requisito, con lo que hoy no está automatizado.
- `DECISIONES.md`: cada decisión con su evidencia y lo que se descartó; incluye Fuera de alcance y Escalado.
- `AI-LOG.md`: dónde hubo que corregir a la IA.
- `docs/perfilado.md`: qué tienen realmente los datos, hallazgo por hallazgo, y las preguntas abiertas al cliente.
- `CHALLENGE.md`: el enunciado.
