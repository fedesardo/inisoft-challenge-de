"""Herramienta del perfilado (docs/perfilado.md).

Dos usos, desde la raíz del repo:

  uv run python docs/herramientas/perfilado.py insertar
      Ejecuta cada consulta SQL de docs/perfilado.md y pega su salida literal
      debajo, en un bloque que empieza con "-- Salida". Se puede repetir: reemplaza
      las salidas anteriores.

  uv run python docs/herramientas/perfilado.py ejecutar "SELECT ..."
      Ejecuta una consulta cualquiera contra las mismas vistas (raw, eq, ot, l, c)
      para hacer tu propio doble check.

Lee drop/ en solo lectura. No escribe nada fuera de docs/perfilado.md.
"""
import re
import sys
from pathlib import Path

import duckdb

RAIZ = Path(__file__).resolve().parents[2]
DOC = RAIZ / "docs" / "perfilado.md"

BLOQUE_SQL = re.compile(r"```sql\n(.*?)\n```", re.S)
SALIDA_PREVIA = re.compile(r"\n\n```text\n-- Salida.*?\n```", re.S)


def conexion():
    """Crea las vistas de la sección 'Preparación' leyendo el propio documento."""
    con = duckdb.connect()
    # Un solo hilo: con varios, las filas empatadas pueden salir en otro orden y
    # las salidas dejarían de ser repetibles.
    con.execute("SET threads=1")
    texto = DOC.read_text()
    prep = next(b for b in BLOQUE_SQL.findall(texto) if "CREATE VIEW raw" in b)
    # Las rutas del documento son relativas a la raíz del repo.
    prep = prep.replace("'drop/", f"'{RAIZ}/drop/")
    for sentencia in dividir(prep):
        con.execute(sentencia)
    return con


def dividir(sql):
    """Separa un bloque en sentencias, ignorando comentarios de línea y vacías."""
    limpio = "\n".join(l.split("--")[0] if l.strip().startswith("--") else l
                       for l in sql.split("\n"))
    return [s.strip() for s in limpio.split(";") if s.strip()]


def formatear(con, sentencia):
    df = con.sql(sentencia).fetchdf()
    return df.to_string(index=False, max_colwidth=90)


def insertar():
    con = conexion()
    texto = DOC.read_text()
    texto = SALIDA_PREVIA.sub("", texto)  # quitar salidas viejas

    def reemplazo(m):
        bloque = m.group(1)
        if "CREATE VIEW" in bloque:
            return m.group(0)
        sentencias = dividir(bloque)
        partes = []
        for i, s in enumerate(sentencias, 1):
            etiqueta = f"-- Salida {i} de {len(sentencias)}" if len(sentencias) > 1 else "-- Salida"
            partes.append(f"{etiqueta}\n{formatear(con, s)}")
        salida = "\n\n".join(partes)
        return f"{m.group(0)}\n\n```text\n{salida}\n```"

    nuevo = BLOQUE_SQL.sub(reemplazo, texto)
    DOC.write_text(nuevo)
    print("salidas insertadas:", nuevo.count("```text\n-- Salida"))


if __name__ == "__main__":
    if len(sys.argv) >= 2 and sys.argv[1] == "insertar":
        insertar()
    elif len(sys.argv) >= 3 and sys.argv[1] == "ejecutar":
        print(formatear(conexion(), sys.argv[2]))
    else:
        print(__doc__)
