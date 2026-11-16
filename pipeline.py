"""Pipeline de limpieza: corre sql/NN_*.sql en orden y, después de cada paso, los tests/NN_*.sql.

Cada test es una consulta que devuelve las filas que rompen una regla: si devuelve alguna,
el pipeline se corta con código 1 y muestra cuáles son. Los pasos que no llegan a correr
quedan registrados como `no_corrio`.

  uv run --locked python pipeline.py              # lee drop/
  DROP_DIR=/ruta/a/otro/drop uv run --locked python pipeline.py

Lee DROP_DIR en solo lectura. Escribe solo en salida/. Sin red ni LLM.
"""
import csv
import os
import re
import sys
import time
from datetime import datetime
from pathlib import Path

import duckdb

RAIZ = Path(__file__).resolve().parent
SALIDA = RAIZ / "salida"
FILAS_MOSTRADAS = 10
CAMPOS_CORRIDAS = ["id_corrida", "drop_dir", "orden", "tipo", "nombre",
                   "estado", "filas", "duracion_s", "mensaje"]


def sentencias(sql):
    """Quita los comentarios de línea y separa por ';'."""
    limpio = re.sub(r"--[^\n]*", "", sql)
    return [s.strip() for s in limpio.split(";") if s.strip()]


def construir_plan():
    """Lista ordenada de (tipo, ruta): cada paso SQL seguido de sus tests."""
    pasos = sorted((RAIZ / "sql").glob("[0-9][0-9]_*.sql"))
    tests = sorted((RAIZ / "tests").glob("[0-9][0-9]_*.sql"))
    prefijos = {p.name[:2] for p in pasos}
    huerfanos = [t.name for t in tests if t.name[:2] not in prefijos]
    if huerfanos:
        sys.exit(f"Tests sin paso SQL con su mismo número: {huerfanos}")
    plan = []
    for paso in pasos:
        plan.append(("sql", paso))
        plan += [("test", t) for t in tests if t.name[:2] == paso.name[:2]]
    return plan


def ejecutar_sql(con, ruta):
    """Corre un paso SQL y devuelve las filas que creó o exportó."""
    filas = 0
    for sentencia in sentencias(ruta.read_text()):
        con.execute(sentencia)
        resultado = con.fetchone() if con.description else None
        if resultado and con.description[0][0] == "Count":
            filas += resultado[0]
    return filas


def ejecutar_test(con, ruta):
    """Corre un test y devuelve (columnas, filas culpables)."""
    con.execute(sentencias(ruta.read_text())[0])
    return [d[0] for d in con.description], con.fetchall()


def guardar_corridas(registros):
    """Agrega las filas al historial (no lo reescribe)."""
    archivo = SALIDA / "corridas.csv"
    nuevo = not archivo.exists()
    with archivo.open("a", newline="") as f:
        w = csv.DictWriter(f, fieldnames=CAMPOS_CORRIDAS)
        if nuevo:
            w.writeheader()
        w.writerows(registros)


def main():
    drop = Path(os.environ["DROP_DIR"]).resolve() if os.environ.get("DROP_DIR") else RAIZ / "drop"
    faltan = [n for n in ("equipos.csv", "ordenes-de-trabajo.csv") if not (drop / n).is_file()]
    if not drop.is_dir() or faltan or not list(drop.glob("lecturas-*.csv")):
        sys.exit(f"{drop} no es un drop válido: hacen falta lecturas-*.csv, {', '.join(faltan) or 'equipos.csv y ordenes-de-trabajo.csv'}")

    os.chdir(RAIZ)  # las rutas de salida en sql/07 son relativas a la raíz del repo
    SALIDA.mkdir(exist_ok=True)
    base = SALIDA / "limpieza.duckdb"
    for sobrante in (base, SALIDA / "limpieza.duckdb.wal"):
        sobrante.unlink(missing_ok=True)

    con = duckdb.connect(str(base))
    con.execute("SET threads=1")  # un solo hilo: el orden de filas empatadas es repetible
    con.execute("SET VARIABLE drop_dir = '" + str(drop).replace("'", "''") + "'")

    id_corrida = datetime.now().isoformat(timespec="seconds")
    plan = construir_plan()
    registros = []
    fallo = False

    for orden, (tipo, ruta) in enumerate(plan, 1):
        nombre = f"{ruta.parent.name}/{ruta.name}"
        reg = {"id_corrida": id_corrida, "drop_dir": str(drop), "orden": orden, "tipo": tipo,
               "nombre": nombre, "estado": "ok", "filas": 0, "duracion_s": 0, "mensaje": ""}
        if fallo:
            reg["estado"] = "no_corrio"
            registros.append(reg)
            continue
        inicio = time.perf_counter()
        try:
            if tipo == "sql":
                reg["filas"] = ejecutar_sql(con, ruta)
            else:
                columnas, culpables = ejecutar_test(con, ruta)
                reg["filas"] = len(culpables)
                if culpables:
                    reg["estado"] = "fallo"
                    reg["mensaje"] = str(dict(zip(columnas, culpables[0])))
                    print(f"\nTEST FALLÓ: {nombre}: {len(culpables)} filas rompen la regla "
                          f"(primeras {min(FILAS_MOSTRADAS, len(culpables))}):")
                    print("  " + " | ".join(columnas))
                    for fila in culpables[:FILAS_MOSTRADAS]:
                        print("  " + " | ".join(str(v) for v in fila))
        except Exception as e:  # error de SQL, archivo ilegible, etc.
            reg["estado"] = "error"
            reg["mensaje"] = str(e).replace("\n", " ")[:500]
            print(f"\nERROR en {nombre}: {e}")
        reg["duracion_s"] = round(time.perf_counter() - inicio, 2)
        registros.append(reg)
        print(f"[{reg['estado']:>5}] {nombre} ({reg['duracion_s']} s)")
        fallo = reg["estado"] != "ok"

    guardar_corridas(registros)
    if fallo:
        pendientes = sum(r["estado"] == "no_corrio" for r in registros)
        print(f"\nPipeline cortado. {pendientes} pasos no corrieron. Detalle en salida/corridas.csv")
        sys.exit(1)

    print("\nAuditoría (salida/auditoria.csv):")
    for fuente, concepto, motivo, filas in con.execute(
            "SELECT * FROM auditoria ORDER BY fuente, "
            "CASE concepto WHEN 'entran' THEN 1 WHEN 'salen' THEN 2 WHEN 'quedan' THEN 3 ELSE 4 END, motivo"
    ).fetchall():
        print(f"  {fuente:9} {concepto:12} {motivo:28} {filas:>8,}".replace(",", "."))
    print(f"\nOK: {len(plan)} pasos y tests. Salidas en salida/")


if __name__ == "__main__":
    main()
