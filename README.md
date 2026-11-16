# Challenge Data Engineering

En construcción: este README se completa al cierre del proyecto.

## Cómo correrlo

Hace falta [uv](https://docs.astral.sh/uv/). Una sola vez: `uv sync`. Después, cualquiera de las dos formas hace lo mismo:

```
make run                      # con make
uv run python pipeline.py     # sin make
```

Cada corrida regenera todo `salida/` desde cero (limpieza, backtest y lista de cierre), sin red y sin LLM. Solo se conserva `salida/corridas.csv`, el historial de corridas. Para procesar otra carpeta de datos: `make run DROP=ruta/al/drop` o `DROP_DIR=ruta/al/drop uv run python pipeline.py`.

## Qué deja en `salida/`

- `lista.csv`: equipos con un episodio de alerta activo en los últimos 3 días de datos, del que más se aparta de su normal al que menos, cada uno con su razón en palabras simples.
- `sobre-umbral.csv`: sección aparte, regla complementaria SU: equipos con la mediana diaria de vibración sobre el umbral del fabricante 2 o más días seguidos, activa en los últimos 3 días, con su razón.
- `sin-datos.csv`: equipos sin lecturas en las últimas 24 h antes del cierre. No son alertas: no hay con qué evaluarlos.
- `backtest.md`, `backtest.csv`, `backtest-fallas.csv`, `backtest-episodios.csv`: la evidencia de que el criterio es confiable.
- `corridas.csv`, `auditoria.csv`, `descartes.csv`, `*.parquet`: bitácora y datos limpios.
