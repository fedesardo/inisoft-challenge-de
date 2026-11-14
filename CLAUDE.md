# Challenge Data Engineering

Telemetría de 40 equipos rotativos (vibración y temperatura) más maestro de umbrales y órdenes de trabajo.
Objetivo: qué equipos mandar a mantenimiento esta semana, con evidencia (backtest) de que la lista es confiable. Enunciado: `CHALLENGE.md`.

## Stack
- Python 3.12 con uv (`uv run ...`). DuckDB con SQL para todo el procesamiento; pandas y plotly solo de apoyo y para el dashboard.

## Reglas
- `drop/` es de solo lectura: son los datos crudos del cliente. Nunca se modifican; todo lo derivado va a `salida/`.
- El pipeline no llama a ningún LLM ni a servicios externos: corre offline con un solo comando.
- Trabajamos por pasos y cada paso se cierra con un commit.
- Errores de la IA → `AI-LOG.md`. Decisiones con su evidencia → `DECISIONES.md`.
