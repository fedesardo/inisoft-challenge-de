# Challenge Data Engineering

En construcción: este README se completa al cierre del proyecto.

## Cómo correrlo

Hace falta [uv](https://docs.astral.sh/uv/). Una sola vez: `uv sync`. Después, cualquiera de las dos formas hace lo mismo:

```
make run                      # con make
uv run python pipeline.py     # sin make
```

Cada corrida regenera todo `salida/` desde cero (limpieza, backtest y lista de cierre), sin red y sin LLM. Solo se conserva `salida/corridas.csv`, el historial de corridas. Para procesar otra carpeta de datos: `make run DROP=ruta/al/drop` o `DROP_DIR=ruta/al/drop uv run python pipeline.py`.

## Tests

```
make test                               # con make
uv run python tests/correr.py           # sin make
```

`make test` vuelve a correr tests sobre lo que ya está en `salida/`, sin regenerar ni escribir nada. Si `salida/` no existe, falla y pide correr `make run` primero.

- **Cubre:** los 8 tests de limpieza (`tests/NN_*.sql`) y el chequeo R8 del dashboard (`tests/dashboard/r8.py`): que no descargue recursos de la red, que contenga cada equipo de la lista y que su recall y su precisión coincidan con `backtest.csv` y `backtest-episodios.csv`.
- **No cubre:** los 5 tests de backtest (`tests/backtest/`) y de lista (`tests/lista/`). Corren solo dentro de `make run`, que se corta con código distinto de 0 si alguno devuelve filas. Para verificar todo, el comando es `make run` (D-36).
- **Límite del chequeo R8:** no ve un script propio que descargue algo al ejecutarse; la prueba final es abrir `salida/dashboard.html` sin internet (D-34).

## Qué deja en `salida/`

- `lista.csv`: equipos con un episodio de alerta activo en los últimos 3 días de datos, del que más se aparta de su normal al que menos, cada uno con su razón en palabras simples.
- `sobre-umbral.csv`: sección aparte, regla complementaria SU: equipos con la mediana diaria de vibración sobre el umbral del fabricante 2 o más días seguidos, activa en los últimos 3 días, con su razón.
- `sin-datos.csv`: equipos sin lecturas en las últimas 24 h antes del cierre. No son alertas: no hay con qué evaluarlos.
- `dashboard.html`: para la jefa de mantenimiento. Una frase con la respuesta y la semana a la que aplica (los 7 días posteriores al último dato), una franja de números con el mapa de la flota, una tarjeta por equipo (acción, por qué, qué cambió, qué tan confiable), la prueba del aviso contra el umbral del fabricante con las fallas una por una, y el detalle plegable por equipo con su gráfico. Abre sin internet; las cifras salen de los CSV de esta carpeta y de `limpieza.duckdb`.
- `backtest.md`, `backtest.csv`, `backtest-fallas.csv`, `backtest-episodios.csv`: la evidencia de que el criterio es confiable.
- `corridas.csv`, `auditoria.csv`, `descartes.csv`, `*.parquet`: bitácora y datos limpios.
