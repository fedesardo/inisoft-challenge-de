# Carpeta de datos crudos a procesar (solo lectura). Uso: make run DROP=otra/carpeta
DROP ?= drop/

.PHONY: run clean

# Corre la limpieza completa (pasos SQL y tests en orden) y después el backtest; se corta si un test devuelve filas.
run:
	DROP_DIR=$(DROP) uv run --locked python pipeline.py
	DROP_DIR=$(DROP) uv run --locked python backtest.py

# Borra salida/ entera, incluido el historial salida/corridas.csv.
clean:
	rm -rf salida
