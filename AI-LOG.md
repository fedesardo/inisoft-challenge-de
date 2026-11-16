# Bitácora de IA

Una fila por cada vez que la IA se equivocó o hubo que corregirla.

| fecha | qué pedí | qué hizo mal | cómo lo detecté | qué cambié |
|---|---|---|---|---|
| 14/11 | Setup con uv y Python 3.12 | `uv init` fijó `requires-python >=3.14` y el pin a 3.12 falló | En el resumen final de Claude | Claude bajó `requires-python` a `>=3.12`; lo revisé y lo acepto. Aprendizaje: revisar `pyproject.toml` después de `uv init` |
| 14/11 | Prueba de edición de `drop/` (agregar una línea a `equipos.csv`) | Nada: Claude se negó por `CLAUDE.md` sin llegar al deny (capa 1) | Pedido de prueba deliberado | El deny ya se había probado al crear un archivo (capa 2). Bash podía saltar el deny: lo cubre `chmod -R a-w drop/` (capa 3) |
| 16/11 | Perfilado de `drop/` (paso 03) | En el primer borrador de `docs/perfilado.md` afirmó "35 de 40 equipos estables y 5 con cambio" sin haberlo calculado (eran 31 y 9), y dijo que las turbinas operan cerca de su umbral sin consulta que lo respalde | Al releer el borrador contra las salidas: la tabla de H-09 mostraba más de 5 equipos con salto, y una consulta de verificación dio 31 estables / 9 que cambian | Claude recalculó con una consulta (31/9), corrigió todas las menciones y quitó la afirmación sobre turbinas. Aprendizaje: toda cifra del documento sale de una consulta citada |
