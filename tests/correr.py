"""make test: vuelve a correr tests sobre lo que ya está en salida/, sin regenerar nada ni escribir nada.

  uv run --locked python tests/correr.py      # código 1 si algún test falla o si falta salida/

Qué cubre: los tests de limpieza (tests/NN_*.sql, sobre salida/limpieza.duckdb en solo lectura) y el chequeo
R8 del dashboard (tests/dashboard/r8.py).
Qué NO cubre: los tests de backtest (tests/backtest/) y de lista (tests/lista/). Usan variables de sesión que
backtest.py y lista.py fijan mientras calculan, así que corren solo dentro de `make run`, que se corta con
código distinto de 0 si alguno devuelve filas (D-36).
"""
import sys
from pathlib import Path

import duckdb

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))
sys.path.insert(0, str(RAIZ / "tests" / "dashboard"))

import r8  # noqa: E402
from pipeline import SALIDA, ejecutar_test  # noqa: E402


def main():
    base = SALIDA / "limpieza.duckdb"
    if not base.is_file() or not (SALIDA / "dashboard.html").is_file():
        sys.exit("Falta salida/ (o está incompleta): corré make run primero")

    fallo = False
    con = duckdb.connect(str(base), read_only=True)
    limpieza = sorted((RAIZ / "tests").glob("[0-9][0-9]_*.sql"))
    for ruta in limpieza:
        columnas, culpables = ejecutar_test(con, ruta)
        print(f"[{'fallo' if culpables else 'ok':>5}] tests/{ruta.name}")
        if culpables:
            print("  " + " | ".join(columnas))
            for fila in culpables[:10]:
                print("  " + " | ".join(str(v) for v in fila))
        fallo = fallo or bool(culpables)
    con.close()

    problemas = r8.revisar(SALIDA)
    print(f"[{'fallo' if problemas else 'ok':>5}] tests/dashboard/r8.py")
    for p in problemas:
        print("  " + p)
    fallo = fallo or bool(problemas)

    fuera = len(list((RAIZ / "tests" / "backtest").glob("*.sql"))) + len(list((RAIZ / "tests" / "lista").glob("*.sql")))
    print(f"\nCubre: {len(limpieza)} tests de limpieza y el chequeo R8 del dashboard, sobre lo ya generado en salida/.")
    print(f"No cubre: los {fuera} tests de backtest y de lista. Esos corren dentro de make run, "
          "que se corta con código distinto de 0 si alguno devuelve filas.")
    if fallo:
        sys.exit(1)
    print("OK: make test")


if __name__ == "__main__":
    main()
