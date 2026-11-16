"""Lista de cierre: qué equipos tienen un episodio activo al final de los datos, y cuáles no tienen datos.

  uv run --locked python lista.py      # requiere salida/limpieza.duckdb y salida/backtest.duckdb

Entra a la lista el equipo con un episodio de la regla principal del backtest cuyo último día de alerta
cae en los últimos N días de datos (config/lista.toml). Se ordena por cuántas veces su señal más
desviada supera su normal. Los equipos sin lecturas recientes van aparte en salida/sin-datos.csv.
Además, en salida/sobre-umbral.csv, la regla complementaria SU (D-31): mediana diaria de vibración
sobre el umbral del fabricante varios días seguidos. Escribe salida/lista.csv, salida/sobre-umbral.csv
y salida/sin-datos.csv. Sin red ni LLM.
"""
import os
import sys
import time
import tomllib
from datetime import datetime
from pathlib import Path

import duckdb

from backtest import coma, fijar
from pipeline import RAIZ, SALIDA, ejecutar_test, guardar_corridas, sentencias

SQL = RAIZ / "sql" / "lista"
TESTS = RAIZ / "tests" / "lista"
SENALES = {"vib": ("Vibración", "mm/s", 3), "temp": ("Temperatura", "°C", 1)}


def frase(senal, desde, normal, actual, veces):
    """Una señal en palabras simples: cuánto sobre su normal, desde cuándo, y los dos valores."""
    nombre, unidad, dec = SENALES[senal]
    return (f"{nombre} a {coma(round(veces, 1), 1)} veces su normal desde el {desde:%d/%m}: "
            f"hoy {coma(round(actual, dec), dec)} {unidad} contra {coma(round(normal, dec), dec)} {unidad} habituales.")


def frase_su(dias, desde, ultimo, mediana, umbral, veces):
    """Una racha sobre el umbral del fabricante, en palabras simples."""
    return (f"Vibración por encima del umbral del fabricante {dias} días seguidos, desde el {desde:%d/%m}: "
            f"mediana del {ultimo:%d/%m} de {coma(round(mediana, 3), 3)} mm/s contra un umbral de {coma(umbral, 1)} mm/s "
            f"({coma(round(veces, 1), 1)} veces el umbral).")


def main():
    for f in ("limpieza.duckdb", "backtest.duckdb"):
        if not (SALIDA / f).is_file():
            sys.exit(f"Falta salida/{f}: corré antes pipeline.py")
    os.chdir(RAIZ)
    cfg = tomllib.loads((RAIZ / "config" / "lista.toml").read_text())
    bt = tomllib.loads((RAIZ / "config" / "backtest.toml").read_text())
    principal = next(c for c in bt["combinaciones"] if c.get("principal"))
    max_equipos = cfg["lista"]["max_equipos"]

    # Se borra lo anterior: si algo falla, no queda una lista vieja que parezca vigente.
    for f in ("lista.csv", "sobre-umbral.csv", "sin-datos.csv"):
        (SALIDA / f).unlink(missing_ok=True)

    con = duckdb.connect(str(SALIDA / "backtest.duckdb"))
    con.execute("SET threads=1")
    con.execute(f"ATTACH '{SALIDA / 'limpieza.duckdb'}' AS limp (READ_ONLY)")
    cierre = con.execute("SELECT max(ts) FROM limp.lecturas").fetchone()[0]
    fijar(con, combo_id=principal["id"], k=float(principal["k"]), cierre=cierre,
          dias_recientes=cfg["lista"]["dias_recientes"], horas_sin_lecturas=cfg["sin_datos"]["horas_sin_lecturas"],
          max_equipos=max_equipos, dias_seguidos=cfg["sobre_umbral"]["dias_seguidos"],
          max_equipos_su=cfg["sobre_umbral"]["max_equipos"])

    registros, id_corrida = [], datetime.now().isoformat(timespec="seconds")
    drop = os.environ.get("DROP_DIR") or "drop/"

    def registrar(tipo, nombre, estado, filas, inicio, mensaje=""):
        registros.append({"id_corrida": id_corrida, "drop_dir": drop, "orden": len(registros) + 1, "tipo": tipo,
                          "nombre": nombre, "estado": estado, "filas": filas,
                          "duracion_s": round(time.perf_counter() - inicio, 2), "mensaje": mensaje})

    inicio = time.perf_counter()
    for s in sentencias((SQL / "lista.sql").read_text()):
        con.execute(s)

    # Una fila por equipo con episodio activo; la señal más desviada manda el orden y las columnas numéricas.
    por_equipo = {}
    for equipo, senal, desde, normal, actual in con.execute(
            "SELECT equipo, senal, desde, normal, valor_actual FROM lista_senales").fetchall():
        por_equipo.setdefault(equipo, []).append((senal, desde, normal, actual, actual / normal))
    maestro = {e: (t, p) for e, t, p in con.execute("SELECT equipment_id, tipo, planta FROM limp.equipos").fetchall()}
    filas = []
    for equipo, senales in por_equipo.items():
        senales.sort(key=lambda s: (-round(s[4], 2), s[0]))
        peor = senales[0]
        filas.append((-round(peor[4], 2), equipo, maestro[equipo][0], maestro[equipo][1], peor[0], peor[1],
                      round(peor[4], 2), peor[3], peor[2], " ".join(frase(*s[:3], s[3], s[4]) for s in senales)))
    filas.sort()
    total_activos = len(filas)
    filas = filas[:max_equipos]

    con.execute("CREATE OR REPLACE TABLE lista_final (puesto INTEGER, equipo VARCHAR, tipo VARCHAR, planta VARCHAR, "
                "senal VARCHAR, desde DATE, veces_sobre_normal DOUBLE, valor_actual DOUBLE, normal DOUBLE, razon VARCHAR)")
    for puesto, (_, *resto) in enumerate(filas, 1):
        con.execute("INSERT INTO lista_final VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", [puesto, *resto])

    # Sección SU: una fila por equipo, de mayor a menor veces sobre el umbral.
    su = []
    for equipo, desde, ultimo, dias, mediana, umbral in con.execute(
            "SELECT equipo, desde, ultimo_dia, dias_seguidos, mediana_ultimo_dia, umbral FROM su_episodios").fetchall():
        veces = round(mediana / umbral, 2)
        su.append((-veces, equipo, maestro[equipo][0], maestro[equipo][1], dias, desde, ultimo, round(mediana, 4), umbral, veces,
                   frase_su(dias, desde, ultimo, mediana, umbral, mediana / umbral)))
    su.sort()
    total_su = len(su)
    su = su[:cfg["sobre_umbral"]["max_equipos"]]
    con.execute("CREATE OR REPLACE TABLE su_final (puesto INTEGER, equipo VARCHAR, tipo VARCHAR, planta VARCHAR, "
                "dias_seguidos INTEGER, desde DATE, ultimo_dia DATE, mediana_ultimo_dia DOUBLE, umbral DOUBLE, "
                "veces_sobre_umbral DOUBLE, razon VARCHAR)")
    for puesto, (_, *resto) in enumerate(su, 1):
        con.execute("INSERT INTO su_final VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", [puesto, *resto])

    registrar("sql", "sql/lista/lista.sql", "ok", len(filas) + len(su), inicio)
    print(f"[   ok] sql/lista: {len(filas)} equipos en la lista, {len(su)} en sobre-umbral, "
          f"{con.execute('SELECT count(*) FROM sin_datos').fetchone()[0]} sin datos")
    if total_su > len(su):
        print(f"AVISO: hay {total_su} equipos sobre el umbral y la sección se recorta a {len(su)}.")
    if total_activos > max_equipos:
        print(f"AVISO: hay {total_activos} episodios activos y la lista se recorta a {max_equipos} (D-04).")

    fallo = False
    for ruta in sorted(TESTS.glob("*.sql")):
        inicio = time.perf_counter()
        columnas, culpables = ejecutar_test(con, ruta)
        estado = "fallo" if culpables else "ok"
        registrar("test", f"tests/lista/{ruta.name}", estado, len(culpables), inicio,
                  str(dict(zip(columnas, culpables[0]))) if culpables else "")
        print(f"[{estado:>5}] tests/lista/{ruta.name}")
        for fila in culpables[:10]:
            print("  " + " | ".join(str(v) for v in fila))
        fallo = fallo or bool(culpables)
    guardar_corridas(registros)
    if fallo:
        sys.exit("Lista cortada: un test devolvió filas. Detalle en salida/corridas.csv")

    con.execute("COPY (SELECT puesto, equipo, tipo, planta, senal, desde, veces_sobre_normal, round(valor_actual, 4) AS valor_actual, round(normal, 4) AS normal, razon "
                "FROM lista_final ORDER BY puesto) TO 'salida/lista.csv' (FORMAT csv, HEADER)")
    con.execute("COPY (SELECT * FROM su_final ORDER BY puesto) TO 'salida/sobre-umbral.csv' (FORMAT csv, HEADER)")
    con.execute("COPY (SELECT equipo, tipo, planta, ultima_lectura, horas_sin_lecturas, "
                "CASE WHEN ultima_lectura IS NULL THEN 'Sin lecturas en todo el drop. No es una alerta: no hay con qué evaluarlo.' "
                "ELSE 'Sin lecturas hace ' || horas_sin_lecturas || ' horas (la última fue el ' || strftime(ultima_lectura, '%d/%m %H:%M') "
                "|| '). No es una alerta: no hay con qué evaluarlo.' END AS razon "
                "FROM sin_datos ORDER BY horas_sin_lecturas DESC NULLS FIRST, equipo) TO 'salida/sin-datos.csv' (FORMAT csv, HEADER)")
    print("\nOK: salida/lista.csv, salida/sobre-umbral.csv y salida/sin-datos.csv")


if __name__ == "__main__":
    main()
