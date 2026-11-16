"""Backtest diario sin fuga: regla propia (cada equipo contra su normal) vs. umbral del fabricante.

  uv run --locked python backtest.py      # requiere salida/limpieza.duckdb (lo crea pipeline.py)

Loop día por día: para cada día evaluado D se crean vistas con WHERE fecha < D + 1 y las reglas
(sql/backtest/) solo leen esas vistas. Parámetros en config/backtest.toml. Escribe en salida/.
Sin red ni LLM.
"""
import os
import sys
import time
import tomllib
from datetime import date, datetime, timedelta
from pathlib import Path

import duckdb

from pipeline import RAIZ, SALIDA, ejecutar_test, guardar_corridas, sentencias

SQL = RAIZ / "sql" / "backtest"
TESTS = RAIZ / "tests" / "backtest"
REGLAS = ("normal.sql", "regla_propia.sql", "regla_fabricante.sql")


def correr(con, nombre):
    for s in sentencias((SQL / nombre).read_text()):
        con.execute(s)


def fijar(con, **variables):
    """SET VARIABLE con valores propios (números, fechas, ids de config): nunca texto del usuario."""
    for nombre, v in variables.items():
        if isinstance(v, bool) or v is None:
            raise ValueError(nombre)
        if isinstance(v, (int, float)):
            lit = f"CAST({v!r} AS DOUBLE)" if isinstance(v, float) else str(v)
        elif isinstance(v, datetime):
            lit = f"TIMESTAMP '{v.isoformat(sep=' ')}'"
        elif isinstance(v, date):
            lit = f"DATE '{v.isoformat()}'"
        else:
            lit = "'" + str(v).replace("'", "''") + "'"
        con.execute(f"SET VARIABLE {nombre} = {lit}")


def coma(x, dec=2):
    """Número con coma decimal; vacío si es None."""
    if x is None:
        return "—"
    return f"{x:.{dec}f}".replace(".", ",") if isinstance(x, float) and x != int(x) else str(int(x))


def informe(con, cfg, primer_dia, ultimo_dia, fin_datos, n_dias):
    cab = ("regla", "fallas_anticipadas_2d", "fallas_con_episodio_7d", "falsas_alarmas",
           "falsas_alarmas_por_semana", "anticipacion_mediana_dias_2d")
    res = con.execute("SELECT * FROM bt_resumen ORDER BY orden").fetchall()
    cols = [d[0] for d in con.description]
    filas = [dict(zip(cols, r)) for r in res]
    principal = next(f for f in filas if f["combo_id"] == cfg["principal"])
    fab = next(f for f in filas if f["combo_id"] == "FAB")

    def nombre(f):
        if f["combo_id"] == "FAB":
            return "Umbral del fabricante (una lectura)"
        return f"Propia {f['combo_id']}: {coma(f['k'])} × normal, {f['lecturas_seguidas']} lecturas seguidas"

    def resumen(f):
        return [
            f"- Fallas anticipadas con al menos 2 días (métrica principal, D-08): **{f['fallas_anticipadas_2d']} de {f['fallas_evaluables']}**.",
            f"- Complementario: fallas con un episodio iniciado en los 7 días previos: **{f['fallas_con_episodio_7d']} de {f['fallas_evaluables']}**. "
            "Incluye avisos de menos de 2 días, que muchas veces no dan tiempo de actuar.",
            f"- Falsas alarmas: **{f['falsas_alarmas']}** en {f['dias_para_falsas_alarmas']} días con 7 días de futuro completo "
            f"(**{coma(f['falsas_alarmas_por_semana'])} por semana**). Episodios sin evaluar por falta de futuro: {f['episodios_sin_evaluar']}.",
            f"- Anticipación mediana (fallas anticipadas ≥ 2 días): {coma(f['anticipacion_mediana_dias_2d'])} días. "
            f"Con todas las que tuvieron episodio en 7 días: {coma(f['anticipacion_mediana_dias_7d'])} días.",
            f"- Episodios: {f['episodios']}, en {f['equipos_marcados']} equipos distintos.",
        ]

    L = ["# Backtest diario: regla propia vs. umbral del fabricante", "",
         f"Días evaluados: {n_dias} (del {primer_dia:%d/%m} al {ultimo_dia:%d/%m}); los primeros {cfg['dias_ventana']} días no se evalúan (no hay normal todavía). "
         f"Último dato: {fin_datos - timedelta(minutes=15):%d/%m %H:%M}. Todo en conteos; ninguna combinación se eligió después de mirar.", "",
         f"## Resultado principal: {nombre(principal)}", ""] + resumen(principal) + ["",
         f"## Referencia: {nombre(fab)}", ""] + resumen(fab) + ["", "## Combinaciones de parámetros", "",
         "| regla | fallas anticipadas ≥ 2 d | fallas con episodio ≤ 7 d | falsas alarmas | falsas alarmas por semana | anticipación mediana (≥ 2 d) |",
         "|---|---|---|---|---|---|"]
    for f in filas:
        L.append(f"| {nombre(f)} | {f['fallas_anticipadas_2d']} de {f['fallas_evaluables']} | {f['fallas_con_episodio_7d']} de {f['fallas_evaluables']} "
                 f"| {f['falsas_alarmas']} | {coma(f['falsas_alarmas_por_semana'])} | {coma(f['anticipacion_mediana_dias_2d'])} |")

    L += ["", "## Cada falla, por regla", "", "| equipo | falla | " + " | ".join(f["combo_id"] for f in filas) + " |",
          "|---|---|" + "---|" * len(filas)]
    fallas = con.execute("SELECT DISTINCT equipment_id, nro_ot, fecha_falla FROM bt_fallas ORDER BY fecha_falla, equipment_id").fetchall()
    for eq, ot, fecha in fallas:
        celdas = []
        for f in filas:
            clase, ant = con.execute("SELECT clase, anticipacion_dias FROM bt_fallas WHERE combo_id=? AND nro_ot=?",
                                     [f["combo_id"], ot]).fetchone()
            celdas.append({"anticipada_2d": f"anticipada, {ant} d", "avisada_menos_2d": f"avisó con {ant} d",
                           "sin_aviso": "sin aviso", "fuera_de_evaluacion": "fuera"}[clase])
        L.append(f"| {eq} | {fecha:%d/%m %H:%M} | " + " | ".join(celdas) + " |")

    fuera = con.execute("SELECT DISTINCT equipment_id, fecha_falla FROM bt_fallas WHERE clase='fuera_de_evaluacion' ORDER BY 2").fetchall()
    L += ["", f"## Fallas fuera de evaluación (antes del {primer_dia:%d/%m}, sin normal)", ""]
    L += [f"- {eq}: {f:%d/%m %H:%M}" for eq, f in fuera] or ["- Ninguna."]
    L += ["", "## Limitaciones", "",
          f"- Con {principal['fallas_evaluables']} fallas, el resultado es evidencia modesta; los cortes diarios se solapan (D-05).",
          "- Un episodio que ya estaba en curso antes de los 7 días previos a una falla no cuenta como acierto de esa falla (el inicio queda fuera de la ventana).",
          "- La racha de lecturas seguidas se mide dentro del día evaluado; una racha que cruza la medianoche se corta.",
          "- El inicio del episodio es el corte del primer día con alerta (00:00 del día siguiente), el momento en que ya se conoce; es conservador.",
          "- Falta la referencia de 5 equipos al azar (R6), la lista semanal (R5) y la ventana P-F (R7): son pasos siguientes."]
    (SALIDA / "backtest.md").write_text("\n".join(L) + "\n")


def main():
    base_limpia = SALIDA / "limpieza.duckdb"
    if not base_limpia.is_file():
        sys.exit("Falta salida/limpieza.duckdb: corré antes pipeline.py")
    for r in REGLAS:  # anti-fuga estructural: las reglas no pueden leer las tablas completas
        if "limp." in (SQL / r).read_text():
            sys.exit(f"{r} lee limp.* directo: las reglas solo pueden usar las vistas")
    os.chdir(RAIZ)
    cfg = tomllib.loads((RAIZ / "config" / "backtest.toml").read_text())
    ventana, dias_min = cfg["normal"]["dias_ventana"], cfg["normal"]["dias_minimos"]
    horizonte, ant_min = cfg["evaluacion"]["horizonte_dias"], cfg["evaluacion"]["anticipacion_minima_dias"]
    combos = cfg["combinaciones"]
    principal = next(c["id"] for c in combos if c.get("principal"))

    base = SALIDA / "backtest.duckdb"
    for sobrante in (base, SALIDA / "backtest.duckdb.wal"):
        sobrante.unlink(missing_ok=True)
    con = duckdb.connect(str(base))
    con.execute("SET threads=1")  # resultado repetible
    con.execute(f"ATTACH '{base_limpia}' AS limp (READ_ONLY)")

    primero, ultimo = con.execute("SELECT CAST(min(ts) AS DATE), CAST(max(ts) AS DATE) FROM limp.lecturas").fetchone()
    primer_dia = primero + timedelta(days=ventana)
    fin_datos = datetime.combine(ultimo + timedelta(days=1), datetime.min.time())
    dias = [primer_dia + timedelta(days=i) for i in range((ultimo - primer_dia).days + 1)]

    fijar(con, dias_ventana=ventana, dias_minimos=dias_min, horizonte=horizonte, ant_min=ant_min,
          primer_dia=primer_dia, fin_datos=fin_datos)
    registros, id_corrida = [], datetime.now().isoformat(timespec="seconds")
    drop = os.environ.get("DROP_DIR") or "drop/"

    def registrar(tipo, nombre, estado, filas, inicio, mensaje=""):
        registros.append({"id_corrida": id_corrida, "drop_dir": drop, "orden": len(registros) + 1, "tipo": tipo,
                          "nombre": nombre, "estado": estado, "filas": filas,
                          "duracion_s": round(time.perf_counter() - inicio, 2), "mensaje": mensaje})

    inicio = time.perf_counter()
    correr(con, "00_tablas.sql")
    con.execute("CREATE TABLE bt_combos (orden INT, combo_id VARCHAR, regla VARCHAR, k DOUBLE, lecturas_seguidas INT)")
    for i, c in enumerate(combos, 1):
        con.execute("INSERT INTO bt_combos VALUES (?, ?, 'propia', ?, ?)", [i, c["id"], float(c["k"]), c["lecturas"]])
    con.execute("INSERT INTO bt_combos VALUES (?, 'FAB', 'fabricante', NULL, NULL)", [len(combos) + 1])

    for dia in dias:  # un día a la vez: cada vuelta solo ve datos con fecha < dia + 1
        fijar(con, dia=dia, corte=dia + timedelta(days=1))
        correr(con, "01_vistas.sql")
        correr(con, "normal.sql")
        for c in combos:
            fijar(con, combo_id=c["id"], k=float(c["k"]), n_min=c["lecturas"])
            correr(con, "regla_propia.sql")
        correr(con, "regla_fabricante.sql")
    correr(con, "episodios.sql")
    correr(con, "metricas.sql")
    filas = con.execute("SELECT count(*) FROM bt_alertas").fetchone()[0]
    registrar("sql", "sql/backtest (loop diario)", "ok", filas, inicio)
    print(f"[   ok] sql/backtest: {len(dias)} días, {filas} alertas día-equipo ({registros[-1]['duracion_s']} s)")

    fallo = False
    for ruta in sorted(TESTS.glob("*.sql")):
        inicio = time.perf_counter()
        nombre = f"tests/backtest/{ruta.name}"
        columnas, culpables = ejecutar_test(con, ruta)
        estado = "fallo" if culpables else "ok"
        registrar("test", nombre, estado, len(culpables), inicio, str(dict(zip(columnas, culpables[0]))) if culpables else "")
        print(f"[{estado:>5}] {nombre}")
        for fila in culpables[:10]:
            print("  " + " | ".join(str(v) for v in fila))
        fallo = fallo or bool(culpables)
    guardar_corridas(registros)
    if fallo:
        sys.exit("Backtest cortado: un test devolvió filas. Detalle en salida/corridas.csv")

    con.execute("COPY (SELECT combo_id, regla, k, lecturas_seguidas, fallas_evaluables, fallas_anticipadas_2d, fallas_con_episodio_7d, "
                "anticipacion_mediana_dias_2d, anticipacion_mediana_dias_7d, episodios, equipos_marcados, falsas_alarmas, "
                "episodios_sin_evaluar, dias_para_falsas_alarmas, falsas_alarmas_por_semana FROM bt_resumen ORDER BY orden) "
                "TO 'salida/backtest.csv' (FORMAT csv, HEADER)")
    con.execute("COPY (SELECT combo_id, equipment_id, nro_ot, fecha_falla, inicio_episodio, anticipacion_dias, clase "
                "FROM bt_fallas ORDER BY orden, fecha_falla, equipment_id) TO 'salida/backtest-fallas.csv' (FORMAT csv, HEADER)")
    con.execute("COPY (SELECT combo_id, equipment_id, primer_dia, ultimo_dia, dias_alerta, inicio, falla, anticipacion_dias, clase "
                "FROM bt_episodios ORDER BY combo_id, equipment_id, primer_dia) TO 'salida/backtest-episodios.csv' (FORMAT csv, HEADER)")
    informe(con, {"principal": principal, "dias_ventana": ventana}, primer_dia, ultimo, fin_datos, len(dias))
    print("\nOK: backtest en salida/backtest.csv, backtest-fallas.csv, backtest-episodios.csv y backtest.md")


if __name__ == "__main__":
    main()
