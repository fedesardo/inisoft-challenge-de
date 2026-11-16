# Carpeta de datos crudos a procesar (solo lectura). Uso: make run DROP=otra/carpeta
DROP ?= drop/

.PHONY: run clean

# Corre la limpieza completa: pasos SQL y tests en orden; se corta si un test devuelve filas.
run:
	DROP_DIR=$(DROP) uv run --locked python pipeline.py

# Borra salida/ entera, incluido el historial salida/corridas.csv.
clean:
	rm -rf salida
