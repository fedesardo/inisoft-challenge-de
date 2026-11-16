"""Genera los gráficos de docs/perfilado.md (H-04, H-07, H-08, H-09).

Uso (desde la raíz del repo):  uv run python docs/graficos/generar_graficos.py

- Lee drop/ en solo lectura con DuckDB; escribe solo los PNG en docs/graficos/.
- Misma lógica que las vistas de la sección "Preparación" de docs/perfilado.md.
- Paleta categórica validada con la guía de dataviz (slots 1-3: azul, naranja, aqua),
  un solo tono secuencial (azul) para el mapa de calor.
"""
import os
import subprocess
import tempfile
from pathlib import Path

import duckdb
import plotly.graph_objects as go
from plotly.subplots import make_subplots

RAIZ = Path(__file__).resolve().parents[2]
SALIDA = Path(__file__).resolve().parent

# Colores por rol (modo claro; los PNG se ven sobre fondo claro).
SUPERFICIE, TEXTO, TEXTO_2, GRILLA = "#fcfcfb", "#0b0b0b", "#52514e", "#e6e5e1"
AZUL, NARANJA, AQUA = "#2a78d6", "#eb6834", "#1baf7a"
FUENTE = dict(family="Helvetica, Arial, sans-serif", color=TEXTO, size=13)

con = duckdb.connect()
con.execute(f"""
CREATE VIEW raw AS SELECT * FROM read_csv('{RAIZ}/drop/lecturas-*.csv',
    union_by_name=true, filename=true, all_varchar=true);
CREATE VIEW l AS SELECT filename, (equipment_id IS NOT NULL) viejo,
    coalesce(equipment_id, asset_id) eqid, coalesce(ts, timestamp) ts_txt,
    coalesce(vibracion_mm_s, vibration_mm_s) vib_txt,
    coalesce(temperatura_c, temp) temp_txt, unidad_temp FROM raw;
CREATE VIEW c AS SELECT filename, viejo, eqid, CAST(ts_txt AS TIMESTAMP) ts,
    CAST(vib_txt AS DOUBLE) vib,
    CASE WHEN unidad_temp='F' THEN (CAST(temp_txt AS DOUBLE)-32)*5/9
         ELSE CAST(temp_txt AS DOUBLE) END temp_c,
    CAST(temp_txt AS DOUBLE) temp_raw, unidad_temp
  FROM l WHERE eqid <> 'EQ-TEST-01';
""")


def base(fig, titulo, ancho, alto):
    fig.update_layout(
        title=dict(text=titulo, x=0.02, xanchor="left", font=dict(size=17)),
        paper_bgcolor=SUPERFICIE, plot_bgcolor=SUPERFICIE, font=FUENTE,
        width=ancho, height=alto, margin=dict(l=60, r=30, t=80, b=60),
    )
    fig.update_xaxes(gridcolor=GRILLA, linecolor=GRILLA, zeroline=False,
                     tickfont=dict(color=TEXTO_2))
    fig.update_yaxes(gridcolor=GRILLA, linecolor=GRILLA, zeroline=False,
                     tickfont=dict(color=TEXTO_2))
    return fig


CHROME = os.environ.get(
    "CHROME_BIN", "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")


def guardar(fig, nombre):
    """PNG vía Chrome headless: kaleido (el exportador estándar) no funciona con
    plotly 7.1.0 (ver AI-LOG.md), y esta vía no suma dependencias."""
    ancho, alto = fig.layout.width, fig.layout.height
    with tempfile.TemporaryDirectory() as tmp:
        html = Path(tmp) / "g.html"
        fig.write_html(str(html), include_plotlyjs=True, full_html=True,
                       default_width=f"{ancho}px", default_height=f"{alto}px",
                       config=dict(staticPlot=True))
        texto = html.read_text().replace(
            "<body>", '<body style="margin:0;background:#fcfcfb">', 1)
        html.write_text(texto)
        subprocess.run(
            [CHROME, "--headless=new", "--disable-gpu", "--hide-scrollbars",
             "--force-device-scale-factor=2", f"--window-size={ancho},{alto}",
             "--virtual-time-budget=4000", f"--screenshot={SALIDA / nombre}",
             f"file://{html}"],
            check=True, capture_output=True)
    print("ok", nombre)


# --- H-07: ciclo diario de temperatura por sistema -----------------------------
h = con.sql("""
SELECT hour(ts) h, avg(temp_c) FILTER (WHERE viejo) viejo,
       avg(temp_c) FILTER (WHERE NOT viejo) nuevo FROM c GROUP BY 1 ORDER BY 1
""").df()
fig = go.Figure()
fig.add_scatter(x=h.h, y=h.viejo, mode="lines+markers", name="Sistema viejo",
                line=dict(color=AZUL, width=2), marker=dict(size=7, line=dict(color=SUPERFICIE, width=2)))
fig.add_scatter(x=h.h, y=h.nuevo, mode="lines+markers", name="Sistema nuevo",
                line=dict(color=NARANJA, width=2), marker=dict(size=7, line=dict(color=SUPERFICIE, width=2)))
fig.add_annotation(x=14.5, y=68.3, text="Pico viejo ≈ 14:30", ax=-70, ay=-35,
                   font=dict(color=TEXTO_2), arrowcolor=AZUL, showarrow=True)
fig.add_annotation(x=17.5, y=68.6, text="Pico nuevo ≈ 17:30", ax=70, ay=-35,
                   font=dict(color=TEXTO_2), arrowcolor=NARANJA, showarrow=True)
base(fig, "H-07 · El ciclo diario de temperatura está corrido ~3 h en el sistema nuevo", 980, 480)
fig.update_xaxes(title="Hora del día (0–23)", dtick=2)
fig.update_yaxes(title="Temperatura promedio (°C)", range=[61.5, 69.5])
fig.update_layout(legend=dict(orientation="h", y=1.08, x=0.02, xanchor="left"))
guardar(fig, "h07-ciclo-diario.png")

# --- H-04: distribución de temperatura, cruda vs. convertida --------------------
CASE = """CASE WHEN viejo THEN 'Viejo (sin unidad)'
          WHEN unidad_temp='F' THEN 'Nuevo marcado °F' ELSE 'Nuevo marcado °C' END"""
colores = {"Viejo (sin unidad)": AZUL, "Nuevo marcado °C": NARANJA, "Nuevo marcado °F": AQUA}
fig = make_subplots(rows=1, cols=2, shared_yaxes=True, horizontal_spacing=0.04,
                    subplot_titles=("Temperatura cruda, como llega", "Temperatura con °F convertido a °C"))
for col, campo in ((1, "temp_raw"), (2, "temp_c")):
    # Porcentaje dentro de cada grupo: los grupos tienen distinta cantidad de filas,
    # y con conteos crudos las curvas tendrían alturas distintas aunque tengan la misma forma.
    d = con.sql(f"""SELECT grupo, b, 100.0*n/sum(n) OVER (PARTITION BY grupo) pct
                    FROM (SELECT {CASE} grupo, floor({campo}) b, count(*) n FROM c GROUP BY 1,2)
                    ORDER BY b""").df()
    for grupo, color in colores.items():
        g = d[d.grupo == grupo]
        fig.add_scatter(x=g.b, y=g.pct, mode="lines", name=grupo, showlegend=(col == 1),
                        line=dict(color=color, width=2), row=1, col=col)
fig.add_annotation(x=105, y=5.5, text="Viejo y nuevo en °C:<br>rango 52–80", font=dict(color=TEXTO_2), showarrow=False, xref="x", yref="y")
fig.add_annotation(x=149, y=5.0, text="°F del nuevo<br>(valores ~150)", font=dict(color=TEXTO_2), showarrow=False, xref="x", yref="y")
fig.add_annotation(x=90, y=5.5, text="Ya convertido, las tres<br>curvas se superponen", font=dict(color=TEXTO_2), showarrow=False, xref="x2", yref="y2")
base(fig, "H-04 · Sin convertir, las lecturas en °F forman otra \"montaña\" a ~150", 1100, 500)
fig.update_xaxes(title="Temperatura tal como llega (°C o °F según la fila)", range=[40, 210],
                 dtick=10, tickangle=-90, row=1, col=1)
fig.update_xaxes(title="Temperatura en °C", range=[40, 100], dtick=5, row=1, col=2)
fig.update_yaxes(title="% de las lecturas del grupo<br>que caen en cada grado", row=1, col=1)
fig.update_layout(legend=dict(orientation="h", y=1.16, x=0.02, xanchor="left"),
                  margin=dict(l=60, r=30, t=110, b=60))
fig.update_annotations(font=dict(color=TEXTO, size=13))
guardar(fig, "h04-unidades.png")

# --- H-09: trayectorias de los equipos que cambian ------------------------------
paneles = [
    ("EQ-115", "vib", "EQ-115 · vibración (mm/s)", 7.1, "umbral 7,1", None),
    ("EQ-102", "temp_c", "EQ-102 · temperatura (°C)", 85.0, "umbral 85", None),
    ("EQ-219", "temp_c", "EQ-219 · temperatura (°C)", None, None, "valor fijo 65,9<br>desde el 25/02"),
    ("EQ-209", "vib", "EQ-209 · vibración (mm/s)", None, None, "cambio de sensor<br>14/02"),
    ("EQ-118", "vib", "EQ-118 · vibración (mm/s)", None, None, "cambio de sensor<br>20/02"),
]
fig = make_subplots(rows=2, cols=3, subplot_titles=[p[2] for p in paneles],
                    horizontal_spacing=0.07, vertical_spacing=0.18)
sensor = {"EQ-209": "2026-02-14", "EQ-118": "2026-02-20"}
for i, (eq, campo, _, umbral, rotulo, nota) in enumerate(paneles):
    r, c_ = i // 3 + 1, i % 3 + 1
    d = con.sql(f"SELECT ts::date d, avg({campo}) v FROM c WHERE eqid='{eq}' GROUP BY 1 ORDER BY 1").df()
    fig.add_scatter(x=d.d, y=d.v, mode="lines", line=dict(color=AZUL, width=2),
                    showlegend=False, row=r, col=c_)
    if umbral:
        fig.add_hline(y=umbral, line=dict(color=TEXTO_2, width=1, dash="dash"),
                      annotation_text=rotulo, annotation_position="top left",
                      annotation_font=dict(color=TEXTO_2, size=11), row=r, col=c_)
    if eq in sensor:
        fig.add_vline(x=sensor[eq], line=dict(color=NARANJA, width=1.5, dash="dot"), row=r, col=c_)
    if nota:
        y_nota = d.v.max() * (0.55 if eq != "EQ-219" else 0.995)
        x_nota = {"EQ-209": "2026-02-21", "EQ-118": "2026-02-26", "EQ-219": "2026-02-08"}[eq]
        fig.add_annotation(x=x_nota, y=y_nota if eq != "EQ-219" else 64.8, text=nota,
                           font=dict(color=TEXTO_2, size=11), showarrow=False,
                           xref=f"x{i + 1 if i else ''}", yref=f"y{i + 1 if i else ''}")
base(fig, "H-09 · Los 5 equipos con cambio más marcado: cada uno se mueve por su cuenta", 1200, 640)
fig.update_xaxes(tickformat="%d/%m", nticks=5)
fig.update_annotations(font=dict(size=12))
guardar(fig, "h09-trayectorias.png")

# --- H-08: lecturas faltantes por equipo y día ----------------------------------
h8 = con.sql("""
SELECT eqid, ts::date d, 96-count(DISTINCT ts) faltan FROM c GROUP BY 1,2
""").df()
con_hueco = h8[h8.faltan > 0].eqid.unique().tolist()
orden = ["EQ-110", "EQ-107", "EQ-112", "EQ-116", "EQ-209", "EQ-214"]
assert set(orden) == set(con_hueco), con_hueco
dias = sorted(h8.d.unique())
# Si un equipo no tiene ninguna fila ese día (EQ-110 el 01/03 y 02/03), faltan las 96.
faltan = {(r.eqid, r.d): int(r.faltan) for r in h8.itertuples()}
z = [[faltan.get((e, d), 96) for d in dias] for e in orden]
texto = [[str(v) if v > 0 else "" for v in fila] for fila in z]
fig = go.Figure(go.Heatmap(
    z=z, x=[d.strftime("%d/%m") for d in dias], y=orden, text=texto, texttemplate="%{text}",
    textfont=dict(size=11), zmin=0, zmax=96, xgap=2, ygap=2,
    colorscale=[[0, "#f1f0ec"], [0.001, "#cfe0f5"], [1, "#0d3b7a"]],
    colorbar=dict(title="Lecturas<br>faltantes", tickfont=dict(color=TEXTO_2)),
))
base(fig, "H-08 · EQ-110 se calla desde el 28/02; los otros 5 tienen un hueco de 8 h el día de su falla", 1100, 420)
fig.update_yaxes(autorange="reversed")
fig.update_xaxes(tickangle=-45, title="Día (2026)")
guardar(fig, "h08-huecos.png")
