# Carpeta de datos crudos a procesar (solo lectura). Uso: make run DROP=otra/carpeta
DROP ?= drop/

.PHONY: run test clean

# Regenera todo desde cero: limpieza (pasos SQL y tests en orden), backtest y lista de cierre.
# Se corta si un test devuelve filas. Equivale a: uv run python pipeline.py
run:
	DROP_DIR=$(DROP) uv run --locked python pipeline.py

# Borra salida/ entera, incluido el historial salida/corridas.csv.
clean:
	rm -rf salida

# Vuelve a correr, sin regenerar nada, los tests de limpieza y el chequeo R8 del dashboard sobre salida/.
# Los tests de backtest y de lista corren solo dentro de `make run` (D-36).
test:
	uv run --locked python tests/correr.py
