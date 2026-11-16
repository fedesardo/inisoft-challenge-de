"""Dashboard: salida/dashboard.html, un solo archivo que abre sin internet (plotly.js embebido).

  uv run --locked python dashboard.py      # requiere salida/ completa (pipeline.py)

Arriba, los tres bloques de la lista de cierre (lista.csv = regla principal, sobre-umbral.csv = SU,
sin-datos.csv), cada uno con su razón y una etiqueta de evidencia sacada de salida/backtest.csv.
Abajo, la comparación de la regla principal contra el umbral del fabricante (FAB), en conteos,
y un gráfico por equipo de las listas: vibración, umbral del fabricante y normal diario.
No calcula reglas: solo lee lo que ya dejaron backtest.py y lista.py. Sin red ni LLM.
"""
import html
import sys
import tomllib

import duckdb
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from pipeline import RAIZ, SALIDA

# Colores (paleta de referencia de dataviz): azul = regla principal y vibración; gris = referencia.
AZUL, NARANJA, GRIS, TINTA, TINTA_2 = "#2a78d6", "#eb6834", "#8a8984", "#0b0b0b", "#52514e"
FUENTE = "system-ui, -apple-system, Segoe UI, sans-serif"


def leer(nombre):
    ruta = SALIDA / nombre
    if not ruta.is_file():
        sys.exit(f"Falta salida/{nombre}: corré antes pipeline.py")
    return pd.read_csv(ruta)


def esc(x):
    return html.escape(str(x))


def evidencia(fila):
    """Etiqueta de evidencia de una regla, con sus conteos del backtest."""
    a, n, fa = int(fila.fallas_anticipadas_2d), int(fila.fallas_evaluables), int(fila.falsas_alarmas)
    alarmas = f"{fa} falsa{'s' if fa != 1 else ''} alarma{'s' if fa != 1 else ''}"
    if a == 0:
        return "sin", f"Sin evidencia de anticipación: anticipó {a} de {n} fallas en el backtest ({alarmas})."
    return "con", f"Anticipó {a} de {n} fallas con al menos 2 días, con {alarmas}, en el backtest."


def bloque(titulo, que_es, etiqueta, filas, vacio):
    clase, texto = etiqueta
    items = "".join(f"<li><b>{esc(f.equipo)}</b> <span class='meta'>{esc(f.tipo)} · {esc(f.planta)}</span>"
                    f"<br>{esc(f.razon)}</li>" for f in filas.itertuples())
    return (f"<section class='bloque'><h2>{esc(titulo)}</h2><p class='que'>{esc(que_es)}</p>"
            f"<p class='etiqueta {clase}'>{esc(texto)}</p>"
            f"<ul>{items or f'<li class=vacio>{esc(vacio)}</li>'}</ul></section>")


def estilo(fig, alto):
    fig.update_layout(height=alto, template="plotly_white", font=dict(family=FUENTE, color=TINTA_2, size=13),
                      margin=dict(l=60, r=20, t=50, b=40), paper_bgcolor="#fcfcfb", plot_bgcolor="#fcfcfb",
                      hoverlabel=dict(font_family=FUENTE))
    fig.update_xaxes(showgrid=False, linecolor="#d6d5d0")
    fig.update_yaxes(gridcolor="#ecebe7", zeroline=False)
    return fig


def comparacion(p, fab, nombre_p):
    """Dos conteos lado a lado; cada uno con su propio eje (son magnitudes distintas)."""
    n = int(p.fallas_evaluables)
    fig = make_subplots(rows=1, cols=2, shared_yaxes=True, horizontal_spacing=0.08, subplot_titles=(
        f"Fallas anticipadas ≥ 2 días (de {n})", "Falsas alarmas"))
    reglas = [nombre_p, "Umbral del fabricante"]
    for col, campo, sufijo in ((1, "fallas_anticipadas_2d", f" de {n}"), (2, "falsas_alarmas", "")):
        valores = [int(getattr(p, campo)), int(getattr(fab, campo))]
        fig.add_bar(row=1, col=col, y=reglas, x=valores, orientation="h", marker_color=[AZUL, GRIS],
                    text=[f"{v}{sufijo}" for v in valores], textposition="outside", cliponaxis=False,
                    hovertemplate="%{y}: %{x}" + sufijo + "<extra></extra>", showlegend=False)
    fig.update_xaxes(range=[0, n], dtick=1, row=1, col=1)
    fig.update_xaxes(rangemode="tozero", row=1, col=2)
    fig.update_yaxes(autorange="reversed", gridcolor="rgba(0,0,0,0)")
    return estilo(fig, 240)


def grafico_equipo(con, equipo, titulo, desde):
    lect = con.execute("SELECT ts, vib_mm_s FROM 'salida/lecturas.parquet' WHERE equipment_id = ? ORDER BY ts",
                       [equipo]).df()
    umbral = con.execute("SELECT umbral_vib_mm_s FROM 'salida/equipos.parquet' WHERE equipment_id = ?",
                         [equipo]).fetchone()[0]
    normal = con.execute("SELECT dia, normal_vib FROM bt.bt_normales WHERE equipment_id = ? ORDER BY dia",
                         [equipo]).df()
    fig = go.Figure()
    if desde is not None:
        fig.add_vrect(x0=pd.Timestamp(desde), x1=lect.ts.max() if len(lect) else pd.Timestamp(desde), fillcolor=NARANJA, opacity=0.08,
                      line_width=0, annotation_text="en alerta", annotation_position="top left",
                      annotation_font_color=TINTA_2)
    fig.add_scatter(x=lect.ts, y=lect.vib_mm_s, mode="lines", name="Vibración (lectura cada 15 min)",
                    line=dict(color=AZUL, width=1), hovertemplate="%{x|%d/%m %H:%M}: %{y:.3f} mm/s<extra></extra>")
    if len(normal):
        # El normal del día D vale para todo D (mediana de los 7 días previos): escalón que arranca en D.
        fig.add_scatter(x=normal.dia, y=normal.normal_vib, mode="lines", line_shape="hv", name="Normal (mediana 7 días previos)",
                        line=dict(color=TINTA, width=2), hovertemplate="normal del %{x|%d/%m}: %{y:.3f} mm/s<extra></extra>")
    fig.add_scatter(x=[lect.ts.min(), lect.ts.max()] if len(lect) else [], y=[umbral, umbral], mode="lines",
                    name=f"Umbral del fabricante ({umbral:g} mm/s)", line=dict(color=NARANJA, width=2, dash="dash"),
                    hovertemplate=f"umbral: {umbral:g} mm/s<extra></extra>")
    fig.update_layout(title=dict(text=titulo, font=dict(color=TINTA, size=15)), hovermode="x unified",
                      legend=dict(orientation="h", y=-0.15), yaxis_title="mm/s")
    return estilo(fig, 360)


def main():
    lista, su, sin = leer("lista.csv"), leer("sobre-umbral.csv"), leer("sin-datos.csv")
    bt = leer("backtest.csv").set_index("combo_id")
    cfg = tomllib.loads((RAIZ / "config" / "backtest.toml").read_text())
    principal = next(c for c in cfg["combinaciones"] if c.get("principal"))
    pid = principal["id"]
    p, fab, su_bt = bt.loc[pid], bt.loc["FAB"], bt.loc["SU"]
    nombre_p = f"Regla {pid} ({principal['k']:g} × normal, {principal['lecturas']} lecturas seguidas)"

    bloques = (
        bloque("Mandar a mantenimiento", f"{nombre_p}: la señal sigue sobre su normal en los últimos días de datos.",
               evidencia(p), lista, "Ningún equipo con alerta activa."),
        bloque("Sobre el umbral del fabricante", "Regla SU: la mediana diaria de vibración supera el umbral del "
               "fabricante varios días seguidos.", evidencia(su_bt), su, "Ningún equipo sobre el umbral."),
        bloque("Sin datos, revisar sensor", "Sin lecturas recientes: no se puede evaluar, no es una alerta.",
               ("nada", "No aplica: no es una predicción, es un control del dato."), sin, "Todos los equipos tienen datos."),
    )

    con = duckdb.connect()
    con.execute(f"ATTACH '{SALIDA / 'backtest.duckdb'}' AS bt (READ_ONLY)")
    figs = [comparacion(p, fab, nombre_p)]
    for f in lista.itertuples():
        figs.append(grafico_equipo(con, f.equipo, f"{f.equipo} · mandar a mantenimiento ({pid})", f.desde))
    for f in su.itertuples():
        figs.append(grafico_equipo(con, f.equipo, f"{f.equipo} · sobre el umbral del fabricante (SU)", f.desde))
    for f in sin.itertuples():
        figs.append(grafico_equipo(con, f.equipo, f"{f.equipo} · sin datos desde {f.ultima_lectura}", None))
    con.close()

    # plotly.js se embebe una sola vez (en la primera figura): el archivo abre sin internet.
    graficos = [fig.to_html(full_html=False, include_plotlyjs=(i == 0), config={"displaylogo": False})
                for i, fig in enumerate(figs)]
    a, n = int(p.fallas_anticipadas_2d), int(p.fallas_evaluables)
    resumen = (f"{pid} anticipó {a} de {n} fallas con {int(p.falsas_alarmas)} falsas alarmas; el umbral del fabricante solo, "
               f"{int(fab.fallas_anticipadas_2d)} de {n} con {int(fab.falsas_alarmas)} falsas alarmas.")
    pagina = f"""<!doctype html>
<html lang="es"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Mantenimiento esta semana</title>
<style>
body {{ background:#fcfcfb; color:{TINTA}; font-family:{FUENTE}; margin:0; padding:24px 16px; }}
main {{ max-width:1100px; margin:0 auto; }}
h1 {{ font-size:22px; margin:0 0 4px; }} h2 {{ font-size:17px; margin:0 0 4px; }}
.sub, .que, .meta {{ color:{TINTA_2}; }} .que {{ margin:0 0 8px; font-size:14px; }}
.bloques {{ display:grid; grid-template-columns:repeat(auto-fit, minmax(280px, 1fr)); gap:16px; margin:20px 0 32px; }}
.bloque {{ border:1px solid #e3e2dd; border-radius:8px; padding:14px 16px; background:#fff; }}
.etiqueta {{ font-size:13px; padding:6px 8px; border-radius:6px; margin:0 0 10px; border-left:4px solid; }}
.etiqueta.con {{ background:#eaf2fc; border-color:{AZUL}; }}
.etiqueta.sin {{ background:#fdf0ea; border-color:{NARANJA}; }}
.etiqueta.nada {{ background:#f1f0ec; border-color:{GRIS}; }}
ul {{ margin:0; padding-left:18px; font-size:14px; }} li {{ margin-bottom:8px; }} .vacio {{ color:{TINTA_2}; }}
.grafico {{ border:1px solid #e3e2dd; border-radius:8px; background:#fcfcfb; margin-bottom:16px; overflow:hidden; }}
</style></head><body><main>
<h1>Qué equipos mandar a mantenimiento</h1>
<p class="sub">Generado por el pipeline desde salida/. Todas las cifras salen de lista.csv, sobre-umbral.csv, sin-datos.csv y backtest.csv.</p>
<div class="bloques">{''.join(bloques)}</div>
<h2>{esc(pid)} contra el umbral del fabricante solo</h2>
<p class="que">{esc(resumen)} Conteos del backtest (salida/backtest.md).</p>
<div class="grafico">{graficos[0]}</div>
<h2>Cada equipo de las listas</h2>
<p class="que">Vibración, su normal (mediana de los 7 días previos, la que usa la regla) y el umbral del fabricante.</p>
{''.join(f'<div class="grafico">{g}</div>' for g in graficos[1:])}
</main></body></html>"""
    (SALIDA / "dashboard.html").write_text(pagina, encoding="utf-8")
    print(f"OK: salida/dashboard.html ({len(figs) - 1} equipos graficados)")


if __name__ == "__main__":
    main()
