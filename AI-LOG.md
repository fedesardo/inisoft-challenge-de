# Bitácora de IA

Una fila por cada vez que la IA se equivocó o hubo que corregirla.

| fecha | qué pedí | qué hizo mal | cómo lo detecté | qué cambié |
|---|---|---|---|---|
| 14/11 | Setup con uv y Python 3.12 | `uv init` fijó `requires-python >=3.14` y el pin a 3.12 falló | En el resumen final de Claude | Claude bajó `requires-python` a `>=3.12`; lo revisé y lo acepto. Aprendizaje: revisar `pyproject.toml` después de `uv init` |
| 14/11 | Prueba de edición de `drop/` (agregar una línea a `equipos.csv`) | Nada: Claude se negó por `CLAUDE.md` sin llegar al deny (capa 1) | Pedido de prueba deliberado | El deny ya se había probado al crear un archivo (capa 2). Bash podía saltar el deny: lo cubre `chmod -R a-w drop/` (capa 3) |
