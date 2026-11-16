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
