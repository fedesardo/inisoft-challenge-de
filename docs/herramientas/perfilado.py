"""Herramienta del perfilado (docs/perfilado.md).

Dos usos, desde la raíz del repo:

  uv run python docs/herramientas/perfilado.py insertar
      Ejecuta cada consulta SQL de docs/perfilado.md y pega su salida debajo, como
      tabla Markdown (las de más de 12 filas, dentro de un desplegable). Se puede
      repetir: reemplaza las salidas anteriores.

  uv run python docs/herramientas/perfilado.py ejecutar "SELECT ..."
      Ejecuta una consulta cualquiera contra las mismas vistas (raw, eq, ot, l, c)
      y la imprime como tabla, para hacer tu propio doble check.

Lee drop/ en solo lectura. No escribe nada fuera de docs/perfilado.md.
"""
import re
import sys
from pathlib import Path

import duckdb

RAIZ = Path(__file__).resolve().parents[2]
DOC = RAIZ / "docs" / "perfilado.md"
FILAS_MAX_VISIBLES = 12  # más filas que esto: la tabla va en un desplegable

BLOQUE_SQL = re.compile(r"```sql\n(.*?)\n```", re.S)
INICIO, FIN = "<!-- salida:inicio -->", "<!-- salida:fin -->"
# Salidas ya insertadas: formato actual (con marcas) y el formato viejo en bloque de texto.
SALIDA_PREVIA = re.compile(
    rf"\n\n{re.escape(INICIO)}.*?{re.escape(FIN)}|\n\n```text\n-- Salida.*?\n```", re.S)


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


def celda(valor):
    """Texto de una celda: NULL explícito, enteros sin '.0', decimales sin ceros de sobra."""
    if valor is None or (isinstance(valor, float) and valor != valor):
        return "NULL"
    if isinstance(valor, float):
        return str(int(valor)) if valor == int(valor) else f"{valor:.4f}".rstrip("0").rstrip(".")
    return str(valor).replace("|", "\\|").replace("\n", " ")


def tabla(con, sentencia):
    """Devuelve (tabla Markdown, cantidad de filas)."""
    df = con.sql(sentencia).fetchdf()
    cols = [str(c).replace("|", "\\|") for c in df.columns]
    lineas = ["| " + " | ".join(cols) + " |", "|" + "|".join("---" for _ in cols) + "|"]
    for fila in df.itertuples(index=False):
        lineas.append("| " + " | ".join(celda(v) for v in fila) + " |")
    return "\n".join(lineas), len(df)


def insertar():
    con = conexion()
    texto = SALIDA_PREVIA.sub("", DOC.read_text())  # quitar salidas viejas

    def reemplazo(m):
        bloque = m.group(1)
        if "CREATE VIEW" in bloque:
            return m.group(0)
        sentencias = dividir(bloque)
        partes = []
        for i, s in enumerate(sentencias, 1):
            etiqueta = f"Salida {i} de {len(sentencias)}" if len(sentencias) > 1 else "Salida"
            t, n = tabla(con, s)
            if n > FILAS_MAX_VISIBLES:
                partes.append(f"<details>\n<summary><b>{etiqueta}</b> ({n} filas, clic para ver)</summary>\n\n{t}\n\n</details>")
            else:
                partes.append(f"**{etiqueta}** ({n} {'fila' if n == 1 else 'filas'})\n\n{t}")
        return f"{m.group(0)}\n\n{INICIO}\n" + "\n\n".join(partes) + f"\n{FIN}"

    nuevo = BLOQUE_SQL.sub(reemplazo, texto)
    DOC.write_text(nuevo)
    print("salidas insertadas:", nuevo.count(INICIO))


if __name__ == "__main__":
    if len(sys.argv) >= 2 and sys.argv[1] == "insertar":
        insertar()
    elif len(sys.argv) >= 3 and sys.argv[1] == "ejecutar":
        print(tabla(conexion(), sys.argv[2])[0])
    else:
        print(__doc__)
