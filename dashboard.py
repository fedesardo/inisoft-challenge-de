"""Dashboard: salida/dashboard.html, un solo archivo que abre sin internet (plotly.js embebido).

  uv run --locked python dashboard.py      # requiere salida/ completa (pipeline.py)

Pensado para la jefa de mantenimiento, que no conoce las reglas ni lee gráficos técnicos:
  1. una frase con la respuesta, la semana a la que aplica y una franja de números;
  2. una tarjeta por equipo: acción, por qué, qué cambió y qué tan confiable es el aviso;
  3. "¿se puede confiar?": veredicto, dos tarjetas de números y las fallas del período una por una;
  4. detalle plegable por equipo, con un gráfico que dice qué mirar.
No calcula reglas: solo lee lo que ya dejaron backtest.py y lista.py (lista.csv, sobre-umbral.csv,
sin-datos.csv, backtest.csv, backtest-fallas.csv, backtest-episodios.csv) y las tablas limpias de limpieza.duckdb. Sin red ni LLM.
"""
import html
import importlib.util
import re
import sys
import tomllib

import duckdb
import pandas as pd
import plotly.graph_objects as go

from pipeline import RAIZ, SALIDA

# Colores (paleta de referencia de dataviz): naranja = mandar a mantenimiento; azul = vibración; gris = referencia.
AZUL, AZUL_TENUE, NARANJA, GRIS, GRIS_CLARO = "#2a78d6", "#b7d3f6", "#eb6834", "#8a8984", "#dcdbd6"
TINTA, TINTA_2, FONDO, BORDE = "#0b0b0b", "#52514e", "#fcfcfb", "#e3e2dd"
FUENTE = "system-ui, -apple-system, Segoe UI, sans-serif"
SENALES = {"vib": ("vib_mm_s", "vibración", "mm/s"), "temp": ("temp_c", "temperatura", "°C")}
TIPOS_OT = {"preventivo": "preventiva", "correctivo": "correctiva", "sin_tipo": "sin tipo"}
DIA_MS = 86_400_000
MAX_TARJETAS = 5  # D-04 para la lista principal; las otras secciones muestran 5 y remiten al CSV
DIAS_SEMANA = 7   # "la semana" = los 7 días posteriores al último dato

NOTAS = RAIZ / "config" / "notas-equipo.toml"  # equipo -> nota; se muestra solo si el equipo está en alguna lista


def leer(nombre):
    ruta = SALIDA / nombre
    if not ruta.is_file():
        sys.exit(f"Falta salida/{nombre}: corré antes pipeline.py")
    return pd.read_csv(ruta)


def esc(x):
    return html.escape(str(x))


def num(x, dec=None):
    """Número con coma decimal. Sin `dec`: 3 decimales bajo 1 (0,213) y 1 decimal desde 1 (9,4)."""
    if dec is None:
        dec = 3 if abs(x) < 1 else 1
    return f"{x:.{dec}f}".replace(".", ",")


def dia(x):
    return pd.Timestamp(x).strftime("%d/%m")


def dia_hora(x):
    return pd.Timestamp(x).strftime("%d/%m a las %H:%M")


def plural(n, uno, varios):
    return f"{n} {uno if n == 1 else varios}"


def enumerar(partes):
    return partes[0] if len(partes) == 1 else ", ".join(partes[:-1]) + " y " + partes[-1]


def falsas(n):
    return "sin falsas alarmas" if n == 0 else f"con {plural(n, 'falsa alarma', 'falsas alarmas')}"


def conteos(fila):
    """Conteos del backtest de una regla. Precisión = avisos acertados sobre avisos que ya se pueden juzgar."""
    juzgables = int(fila.episodios) - int(fila.episodios_sin_evaluar)
    return dict(a=int(fila.fallas_anticipadas_2d), n=int(fila.fallas_evaluables), fa=int(fila.falsas_alarmas),
                avisos=int(fila.episodios), recientes=int(fila.episodios_sin_evaluar), juzgables=juzgables,
                acertados=juzgables - int(fila.falsas_alarmas))


# ---------- Datos de apoyo (solo lectura de limpieza.duckdb) ----------

def cambio_de_sensor(con, equipo):
    """OT de cambio de sensor del equipo, si la hay: (nro_ot, fecha, modelo nuevo). Solo para presentar (D-16)."""
    fila = con.execute(
        "SELECT nro_ot, fecha_apertura, descripcion FROM ot WHERE equipment_id = ? "
        "AND regexp_matches(lower(descripcion), '(cambio|reemplazo).*sensor') ORDER BY fecha_apertura DESC LIMIT 1",
        [equipo]).fetchone()
    if not fila:
        return None
    modelo = re.search(r"VX-\d+", fila[2])
    return {"ot": fila[0], "fecha": pd.Timestamp(fila[1]), "modelo": modelo.group(0) if modelo else "nuevo"}


def medianas_diarias(con, equipo, col="vib_mm_s"):
    df = con.execute(f"SELECT ts::date AS d, median({col}) AS v FROM lecturas WHERE equipment_id = ? AND {col} IS NOT NULL "
                     "GROUP BY 1 ORDER BY 1", [equipo]).df()
    return pd.Series(df.v.values, index=pd.to_datetime(df.d))


def ots_con_efecto(con, equipo, diaria):
    """OT del equipo con la mediana del día anterior y del día siguiente. No se copia la descripción de la OT."""
    ots = con.execute("SELECT nro_ot, fecha_apertura, tipo FROM ot WHERE equipment_id = ? ORDER BY fecha_apertura", [equipo]).fetchall()
    salida = []
    for nro, fecha, tipo in ots:
        d = pd.Timestamp(fecha).normalize()
        antes, despues = diaria.get(d - pd.Timedelta(days=1)), diaria.get(d + pd.Timedelta(days=1))
        if antes is not None and despues is not None:
            salida.append(dict(ot=nro, fecha=pd.Timestamp(fecha), tipo=TIPOS_OT.get(tipo, tipo), antes=antes, despues=despues))
    return salida


# ---------- Tarjetas por equipo ----------

def armar_filas(con, lista, su, sin, p, pid, periodo, notas_equipo):
    """Una entrada por equipo: a quién, qué hacer, por qué, qué cambió y qué tan confiable. Guion también de los gráficos."""
    filas, c = [], conteos(p)
    conf_p = (f"Evidencia modesta: avisó {c['a']} de {c['n']} fallas del {periodo}, {falsas(c['fa'])}" if c["a"]
              else f"Sin evidencia todavía: avisó 0 de {c['n']} fallas del {periodo}")
    for f in lista.head(MAX_TARJETAS).itertuples():
        _, nombre, unidad = SENALES[f.senal]
        sensor, notas = cambio_de_sensor(con, f.equipo), []
        if sensor:
            notas.append(f"Medido con el sensor {sensor['modelo']} instalado el {dia(sensor['fecha'])}, cuya escala todavía no está validada.")
        filas.append(dict(
            equipo=f.equipo, tipo=f.tipo, planta=f.planta, clase="mant", accion="Mandar a mantenimiento", sigla=f"regla {pid}",
            porque=f"Su {nombre} viene subiendo desde el {dia(f.desde)} y ya está a {num(f.veces_sobre_normal, 1)} veces su nivel habitual.",
            cambio=(("Nivel habitual", f"{num(f.normal)} {unidad}"), ("Últimas 24 h", f"{num(f.valor_actual)} {unidad}")),
            notas=notas, confianza=conf_p, dato=f, sensor=sensor))
    for f in su.head(MAX_TARJETAS).itertuples():
        diaria = medianas_diarias(con, f.equipo)
        ultimo = pd.Timestamp(f.ultimo_dia)
        hace7 = diaria.get(ultimo - pd.Timedelta(days=7))
        notas = [f"Tuvo una OT {o['tipo']} el {dia(o['fecha'])} y la vibración siguió subiendo: de {num(o['antes'])} mm/s el día "
                 f"anterior a {num(o['despues'])} el día siguiente (D-30)."
                 for o in ots_con_efecto(con, f.equipo, diaria) if o["fecha"] >= pd.Timestamp(f.desde) and o["despues"] > o["antes"]]
        filas.append(dict(
            equipo=f.equipo, tipo=f.tipo, planta=f.planta, clase="umbral", sigla="regla SU",
            accion="Revisar vibración sobre el límite del fabricante",
            porque=f"Lleva {plural(int(f.dias_seguidos), 'día', 'días seguidos')} vibrando por encima del límite que fija el "
                   f"fabricante ({num(f.umbral)} mm/s).",
            cambio=((f"Hace 7 días ({dia(ultimo - pd.Timedelta(days=7))})", f"{num(hace7)} mm/s" if hace7 is not None else "sin dato"),
                    (f"Último día ({dia(ultimo)})", f"{num(f.mediana_ultimo_dia)} mm/s")),
            notas=notas, confianza="Sin evidencia todavía: esta regla se agregó después de ver el caso (D-31)", dato=f, sensor=None))
    for f in sin.head(MAX_TARJETAS).itertuples():
        if pd.isna(f.ultima_lectura):  # sin ninguna lectura en todo el drop
            umbral = con.execute("SELECT umbral_vib_mm_s FROM equipos WHERE equipment_id = ?", [f.equipo]).fetchone()[0]
            filas.append(dict(
                equipo=f.equipo, tipo=f.tipo, planta=f.planta, clase="sensor", accion="Revisar el sensor", sigla="sin datos",
                porque="No mandó ninguna lectura en todo el período: no sabemos cómo está.",
                cambio=(("Antes del corte", "sin lecturas"), ("En todo el período", "sin lecturas")),
                notas=[], confianza="No es una predicción: es un control del dato", dato=f, sensor=None, previo=None, umbral=umbral))
            continue
        ultima = pd.Timestamp(f.ultima_lectura)
        previo, umbral = con.execute(
            "SELECT (SELECT median(vib_mm_s) FROM lecturas WHERE equipment_id = ? AND ts > ?::TIMESTAMP - INTERVAL 7 DAY), "
            "(SELECT umbral_vib_mm_s FROM equipos WHERE equipment_id = ?)", [f.equipo, ultima, f.equipo]).fetchone()
        filas.append(dict(
            equipo=f.equipo, tipo=f.tipo, planta=f.planta, clase="sensor", accion="Revisar el sensor", sigla="sin datos",
            porque=f"Dejó de mandar lecturas el {dia_hora(ultima)}: hace {int(f.horas_sin_lecturas)} horas que no sabemos cómo está.",
            cambio=(("Antes del corte", f"{num(previo)} mm/s"), (f"Desde el {dia(ultima)}", "sin lecturas")),
            notas=[], confianza="No es una predicción: es un control del dato", dato=f, sensor=None, previo=previo, umbral=umbral))
    for fila in filas:
        if fila["equipo"] in notas_equipo:
            fila["notas"].append(notas_equipo[fila["equipo"]])
    return filas


def html_tarjetas(filas, su, sin):
    bloques = ""
    for f in filas:
        (r1, v1), (r2, v2) = f["cambio"]
        notas = "".join(f"<p class='nota'>{esc(n)}</p>" for n in f["notas"])
        bloques += (
            f"<article class='equipo {f['clase']}'><header><span class='accion'>{esc(f['accion'])}</span>"
            f"<span class='quien'><b>{esc(f['equipo'])}</b> · {esc(f['tipo'])} · {esc(f['planta'])} <small>· {esc(f['sigla'])}</small></span></header>"
            "<div class='cuerpo'>"
            f"<div><h4>Por qué</h4><p>{esc(f['porque'])}</p></div>"
            f"<div><h4>Qué cambió</h4><p class='cambio'><span><small>{esc(r1)}</small><b>{esc(v1)}</b></span>"
            f"<span class='flecha'>→</span><span><small>{esc(r2)}</small><b>{esc(v2)}</b></span></p></div>"
            f"<div><h4>Qué tan confiable</h4><p>{esc(f['confianza'])}</p></div>"
            f"</div>{notas}</article>")
    for df, archivo in ((su, "sobre-umbral.csv"), (sin, "sin-datos.csv")):
        if len(df) > MAX_TARJETAS:
            bloques += f"<p class='chica'>… y {len(df) - MAX_TARJETAS} más en {archivo}.</p>"
    return bloques or "<p>Nada para atender.</p>"


def frase_respuesta(lista, su, sin, total, semana):
    partes = []
    for df, texto in ((lista, "mandar {n} a mantenimiento ({eq})"), (su, "revisar {n} por vibración alta ({eq})"),
                      (sin, "revisar el sensor de {n} ({eq})")):
        if len(df):
            partes.append(texto.format(n=len(df), eq=", ".join(df.equipo)))
    n = len(set(lista.equipo) | set(su.equipo) | set(sin.equipo))
    if not n:
        return f"Del {semana} no hay equipos para atender: ninguno de los {total} tiene avisos."
    return f"Del {semana} hay <b>{plural(n, 'equipo', 'equipos')} para atender</b>: {esc(enumerar(partes))}."


def html_franja(con, lista, su, sin, total):
    """Cuatro números grandes y el mapa de la flota: un cuadradito por equipo, coloreado por su estado."""
    estado = {e: ("sensor", "Revisar el sensor") for e in sin.equipo}
    estado |= {e: ("umbral", "Revisar vibración alta") for e in su.equipo}
    estado |= {e: ("mant", "Mandar a mantenimiento") for e in lista.equipo}
    cifras = "".join(f"<div class='cifra {c}'><span class='grande'>{n}</span><span class='rotulo'>{esc(t)}</span></div>" for c, n, t in (
        ("total", total, "equipos monitoreados"), ("mant", len(lista), "mandar a mantenimiento"),
        ("umbral", len(su), "revisar vibración alta"), ("sensor", len(sin), "revisar sensor")))
    resto = total - len(estado)
    otros = "El otro equipo no tiene avisos." if resto == 1 else f"Los otros {resto} equipos no tienen avisos."
    cuadros = "".join(
        f"<i class='{estado.get(e, ('ok', ''))[0]}' title='{esc(e)} · {esc(t)} · {esc(estado.get(e, ('', 'Sin avisos'))[1])}'></i>"
        for e, t in con.execute("SELECT equipment_id, tipo FROM equipos ORDER BY 1").fetchall())
    leyenda = "".join(f"<span><i class='{c}'></i>{t}</span>" for c, t in (
        ("mant", "Mandar a mantenimiento"), ("umbral", "Revisar vibración alta"), ("sensor", "Revisar sensor"), ("ok", "Sin avisos")))
    return (f"<div class='franja'>{cifras}</div><p>{otros if resto > 0 else ''}</p>"
            f"<div class='flota' role='img' aria-label='Mapa de la flota: un cuadrado por equipo'>{cuadros}</div>"
            f"<p class='chica leyenda'>Cada cuadrado es un equipo (pasá el mouse para ver cuál). {leyenda}</p>")


# ---------- Evidencia: dos números y las fallas una por una ----------

def texto_precision(c, a_tiempo, tarde_dias, minimo, horizonte):
    """Precisión en palabras, sin porcentajes (D-34). Plantilla sobre los conteos de backtest.csv (c) y el desglose de
    backtest-episodios.csv: aciertos con `minimo` días o más (a_tiempo) y días de anticipación de los tardíos (tarde_dias)."""
    avisos, juzgables, acertados, fa, recientes = c["avisos"], c["juzgables"], c["acertados"], c["fa"], c["recientes"]
    tarde = len(tarde_dias)
    cuando = "el mismo día de la falla" if all(d == 0 for d in tarde_dias) else f"con menos de {minimo} días"
    con_margen = f"con {minimo} o más días de anticipación"
    de_sus = "Su único aviso" if avisos == 1 else f"De sus {avisos} avisos, {juzgables}"
    if juzgables == 0:
        texto = f"Dio {plural(avisos, 'aviso', 'avisos')} y todavía ninguno se puede juzgar."
    elif fa == 0:  # todos los juzgables terminaron en falla
        if avisos == 1 or juzgables == 1:
            texto = f"{de_sus} ya se puede juzgar y terminó en falla dentro de los {horizonte} días"
        else:
            texto = f"{de_sus} ya se pueden juzgar y los {juzgables} terminaron en falla dentro de los {horizonte} días"
        if tarde == 0:
            texto += f", {'siempre ' if acertados > 1 else ''}{con_margen}."
        elif a_tiempo == 0:
            texto += f", {'pero ' if acertados == 1 else f'pero los {tarde} '}{cuando} (tarde)."
        else:
            texto += (f". Pero solo {a_tiempo} {'llegó' if a_tiempo == 1 else 'llegaron'} {con_margen}; "
                      f"{'el otro llegó' if tarde == 1 else f'los otros {tarde} llegaron'} {cuando} (tarde).")
    else:
        texto = f"{de_sus} ya se {'puede' if juzgables == 1 else 'pueden'} juzgar: "
        if acertados == 0:
            texto += "ninguno terminó en falla"
        else:
            texto += f"{acertados} {'terminó' if acertados == 1 else 'terminaron'} en falla dentro de los {horizonte} días"
            if tarde == 0:
                texto += f", {'' if acertados == 1 else f'los {acertados} '}{con_margen},"
            elif a_tiempo == 0:
                texto += f", {'' if acertados == 1 else f'los {tarde} '}{cuando} (tarde),"
            else:
                texto += f" ({a_tiempo} {con_margen} y {tarde} {cuando}, tarde)"
        texto += f" y {fa} {'fue falsa alarma' if fa == 1 else 'fueron falsas alarmas'}."
    if recientes and juzgables:
        texto += (" El otro aviso es muy reciente para saberlo." if recientes == 1
                  else f" Los otros {recientes} avisos son muy recientes para saberlo.")
    return texto


def tarjeta(titulo, regla, fila, clase, episodios, minimo, horizonte):
    c = conteos(fila)
    propios = episodios[episodios.combo_id == regla]
    a_tiempo = int((propios.clase == "acierto_2_7").sum())
    tarde_dias = [int(d) for d in propios[propios.clase == "acierto_0_1"].anticipacion_dias]
    precision = texto_precision(c, a_tiempo, tarde_dias, minimo, horizonte)
    return (f"<div class='tarjeta {clase}' data-regla='{esc(regla)}' data-recall='{c['a']}/{c['n']}' "
            f"data-precision='{c['acertados']}/{c['juzgables']}' data-falsas='{c['fa']}' data-a-tiempo='{a_tiempo}' "
            f"data-tarde='{len(tarde_dias)}' data-recientes='{c['recientes']}'><h3>{esc(titulo)}</h3><div class='cifras'>"
            f"<div><span class='grande'>{c['a']} de {c['n']}</span><span class='rotulo'>fallas avisadas</span></div>"
            f"<div><span class='grande'>{c['fa']}</span><span class='rotulo'>{'falsa alarma' if c['fa'] == 1 else 'falsas alarmas'}</span></div>"
            f"</div><p class='precision'>{esc(precision)}</p></div>")


def veredicto(p, fab):
    c, f = conteos(p), conteos(fab)
    propio = f"avisó {c['a']} de {c['n']} fallas " + ("sin ninguna falsa alarma" if c["fa"] == 0 else falsas(c["fa"]))
    otro = (f"mirar solo el umbral del fabricante {'no avisó ninguna' if f['a'] == 0 else f'avisó {f[chr(97)]}'} y se equivocó "
            f"{plural(f['fa'], 'vez', 'veces')}")
    titular = "Avisa poco, pero no molesta: " if c["fa"] == 0 and 0 < c["a"] < c["n"] else "Resultado de la prueba: "
    return f"{titular}{propio}; {otro}."


def aviso(f):
    if f.clase == "sin_aviso":
        return "<span class='no'>No avisó</span>"
    if f.clase == "fuera_de_evaluacion":
        return "<span class='no'>No evaluada (fuera del período de la prueba)</span>"
    d = int(f.anticipacion_dias)
    if f.clase == "anticipada_2d":
        return f"<span class='si'>✓ Avisó {d} días antes</span>"
    return f"<span class='tarde'>Avisó tarde ({'el mismo día' if d == 0 else plural(d, 'día antes', 'días antes')})</span>"


def html_fallas(fallas, pid):
    propia = fallas[fallas.combo_id == pid].set_index("nro_ot")
    fab = fallas[fallas.combo_id == "FAB"].set_index("nro_ot")
    filas = "".join(
        f"<tr><td data-t='Equipo'><b>{esc(f.equipment_id)}</b></td><td data-t='Falló el'>{dia(f.fecha_falla)}</td>"
        f"<td data-t='Nuestro aviso'>{aviso(f)}</td><td data-t='Solo el umbral'>{aviso(fab.loc[ot]) if ot in fab.index else '—'}</td></tr>"
        for ot, f in propia.iterrows())
    return ("<table class='fallas'><thead><tr><th>Equipo</th><th>Falló el</th><th>Nuestro aviso de mantenimiento</th>"
            f"<th>Solo el umbral del fabricante</th></tr></thead><tbody>{filas}</tbody></table>")


# ---------- Detalle por equipo ----------

def etiqueta(fig, x, texto, lado="left", arriba=True):
    fig.add_annotation(x=x, y=1.0 if arriba else 0.0, yref="paper", text=texto, showarrow=False, xanchor=lado, yanchor="bottom",
                       xshift=4 if lado == "left" else -4, font=dict(color=TINTA_2, size=12))


def grafico_equipo(con, f, cierre, k):
    """Devuelve (título que dice qué mirar, líneas al pie, figura) para un equipo con aviso de vibración o de regla."""
    d, equipo, sensor = f["dato"], f["equipo"], f["sensor"]
    col, nombre, unidad = SENALES[getattr(d, "senal", "vib")]
    lect = con.execute(f"SELECT ts, {col} AS v FROM lecturas WHERE equipment_id = ? AND {col} IS NOT NULL ORDER BY ts", [equipo]).df()
    umbral = con.execute("SELECT umbral_vib_mm_s, umbral_temp_c FROM equipos WHERE equipment_id = ?",
                         [equipo]).fetchone()[0 if col == "vib_mm_s" else 1]
    fig, pie, x0 = go.Figure(), [], lect.ts.min()
    # Aviso de la regla propia: el eje va en veces el nivel habitual del equipo (1× = el normal de lista.csv).
    relativo = f["clase"] == "mant"
    base = float(d.normal) if relativo else 1.0
    sufijo = "×" if relativo else f" {unidad}"

    if sensor:
        # La escala cambia con el sensor: se dibuja solo lo medido con el nuevo. El salto de escala es la primera
        # lectura posterior a la OT por debajo de la mitad del nivel anterior (llega unas horas después de la OT).
        antes = lect[lect.ts < sensor["fecha"]]
        previo = antes[antes.ts >= sensor["fecha"] - pd.Timedelta(days=3)].v.median()
        despues = lect[(lect.ts >= sensor["fecha"]) & (lect.v < previo / 2)]
        salto = despues.ts.min() if len(despues) else sensor["fecha"]
        lect = lect[lect.ts >= salto]
        x0 = salto - pd.Timedelta(days=2)
        fig.add_vrect(x0=x0, x1=salto, fillcolor=GRIS, opacity=0.10, line_width=0)
        fig.add_vline(x=salto, line=dict(color=TINTA, width=1.5))
        etiqueta(fig, salto, f"Cambio de sensor · {dia(sensor['fecha'])} (OT {sensor['ot']})")
        fig.add_annotation(x=x0 + (salto - x0) / 2, y=0.5, yref="paper", showarrow=False, font=dict(color=TINTA_2, size=12),
                           text=f"Sensor anterior<br>≈ {num(previo)} {unidad}<br>(otra escala,<br>no se dibuja)")

    diaria = lect.groupby(lect.ts.dt.floor("D")).v.median().reset_index()
    diaria["ts"] += pd.Timedelta(hours=12)  # el punto del día va al mediodía, sobre sus lecturas

    # Eje limitado: lo fija la tendencia (medianas y percentil 99), no los picos aislados.
    dibujar_umbral = not sensor
    referencias = [diaria.v.max(), lect.v.quantile(0.99)] + ([umbral] if dibujar_umbral else []) + ([k * base] if relativo else [])
    techo = 1.18 * max(referencias)
    fuera = lect[lect.v > techo]

    desde = pd.Timestamp(d.desde)
    fig.add_vrect(x0=desde, x1=cierre, fillcolor=NARANJA, opacity=0.09, line_width=0)
    etiqueta(fig, desde, f"En alerta desde el {dia(desde)}" if relativo else f"Sobre el límite desde el {dia(desde)}", arriba=relativo)

    plantilla = f"%{{y:.2f}}× (%{{customdata:.3f}} {unidad})" if relativo else f"%{{y:.3f}} {unidad}"
    fig.add_scatter(x=lect.ts, y=lect.v / base, customdata=lect.v, mode="lines", name="Lecturas cada 15 min",
                    line=dict(color=AZUL_TENUE, width=1), hovertemplate=plantilla + "<extra>lectura</extra>")
    fig.add_scatter(x=diaria.ts, y=diaria.v / base, customdata=diaria.v, mode="lines+markers", name="Vibración típica de cada día" if col == "vib_mm_s" else "Valor típico de cada día",
                    line=dict(color=AZUL, width=2.5), marker=dict(size=7, color=AZUL, line=dict(color=FONDO, width=2)),
                    hovertemplate=plantilla + "<extra>típico del día</extra>")

    def referencia(y, texto, trazo, arriba=True, lado="left"):
        fig.add_hline(y=y / base, line=dict(color=TINTA_2, width=1.5, dash=trazo))
        fig.add_annotation(x=0 if lado == "left" else 1, xref="paper", y=y / base, text=texto, showarrow=False, xanchor=lado,
                           yanchor="bottom" if arriba else "top", xshift=6 if lado == "left" else -6, font=dict(color=TINTA_2, size=12))

    if relativo:
        referencia(base, f"Nivel habitual: 1× = {num(base)} {unidad}", "dot", arriba=False, lado="right")
        referencia(k * base, f"Desde acá avisamos: {num(k, 1)}×", "dash", lado="right")
    if dibujar_umbral:
        referencia(umbral, f"Límite del fabricante: {num(umbral)} {unidad}" + (f" ({num(umbral / base, 1)}×)" if relativo else ""), "dash")

    if not relativo:  # órdenes de trabajo del equipo: ayudan a leer saltos de la señal
        medianas = medianas_diarias(con, equipo, col)
        for o in ots_con_efecto(con, equipo, medianas):
            fig.add_vline(x=o["fecha"], line=dict(color=TINTA_2, width=1, dash="dot"))
            etiqueta(fig, o["fecha"], f"OT {o['ot']} · {dia(o['fecha'])}", lado="right")
            if o["despues"] < o["antes"]:
                pie.append(f"La baja de alrededor del {dia(o['fecha'])} coincide con la OT {o['tipo']} {o['ot']} de ese día: el valor típico "
                           f"pasó de {num(o['antes'])} {unidad} el día anterior a {num(o['despues'])} el día siguiente. Qué se hizo está en la orden.")
            else:
                pie.append(f"La OT {o['tipo']} {o['ot']} del {dia(o['fecha'])} no frenó la subida: de {num(o['antes'])} {unidad} el día anterior "
                           f"a {num(o['despues'])} el día siguiente.")

    fig.update_layout(
        height=340, template="plotly_white", font=dict(family=FUENTE, color=TINTA_2, size=13), separators=",.",
        margin=dict(l=56, r=16, t=30, b=36), paper_bgcolor=FONDO, plot_bgcolor=FONDO, hovermode="x unified",
        hoverlabel=dict(font_family=FUENTE), dragmode=False,
        legend=dict(orientation="h", y=-0.14, x=0, traceorder="reversed"))
    fig.update_xaxes(range=[x0, cierre + pd.Timedelta(hours=6)], showgrid=False, linecolor="#d6d5d0", tickformat="%d/%m",
                     dtick=(2 if sensor else 4) * DIA_MS, hoverformat="%d/%m %H:%M", fixedrange=True)
    fig.update_yaxes(range=[0, techo / base], gridcolor="#ecebe7", zeroline=False, fixedrange=True,
                     title_text="veces su nivel habitual" if relativo else unidad, ticksuffix="×" if relativo else "")

    if len(fuera):
        pie.append(f"{plural(len(fuera), 'lectura aislada queda', 'lecturas aisladas quedan')} fuera del eje "
                   f"(máximo {num(fuera.v.max() / base)}{sufijo}): se recortan para que no aplasten la tendencia.")

    if relativo:
        titulo = (f"{equipo}: mirá cómo la línea azul se despega de su nivel habitual"
                  + (" después del cambio de sensor" if sensor else "") + f" y llega a {num(d.veces_sobre_normal, 1)} veces")
        pie.insert(0, f"El eje va en veces su nivel habitual: 1× = {num(base)} {unidad}, el nivel habitual del {dia(desde)}, día en que "
                      f"empezó la alerta (D-30). El aviso salta cuando la señal pasa {num(k, 1)}× varias lecturas seguidas.")
        if sensor:
            pie.insert(1, f"No se dibuja el límite del fabricante ({num(umbral)} {unidad}): el sensor {sensor['modelo']} mide en otra "
                          "escala, que todavía no está validada con el proveedor (D-16). Por eso se compara al equipo consigo mismo.")
    else:
        titulo = (f"{equipo}: mirá cómo la línea azul cruza el límite del fabricante el {dia(desde)} y sigue arriba "
                  f"({num(d.mediana_ultimo_dia)} contra {num(d.umbral)} mm/s)")
    return titulo, pie, fig


def html_detalle(con, filas, cierre, k):
    """Un <details> cerrado por equipo con gráfico; los equipos sin datos van como una línea de texto."""
    bloques, primero = "", True
    for f in filas:
        if f["clase"] == "sensor" and (f["previo"] is None or pd.isna(f["previo"])):
            bloques += (f"<p class='sin-grafico'><b>{esc(f['equipo'])}</b>: sin gráfico, no mandó ninguna lectura "
                        "en todo el período.</p>")
            continue
        if f["clase"] == "sensor":
            d, bajo = f["dato"], f["previo"] < f["umbral"]
            bloques += (f"<p class='sin-grafico'><b>{esc(f['equipo'])}</b>: sin gráfico, no hay nada que mirar. Vibraba en torno a "
                        f"{num(f['previo'])} mm/s ({'por debajo' if bajo else 'por encima'} del límite del fabricante, {num(f['umbral'])}) "
                        f"hasta que dejó de mandar lecturas el {dia_hora(d.ultima_lectura)}.</p>")
            continue
        titulo, pie, fig = grafico_equipo(con, f, cierre, k)
        # plotly.js se embebe una sola vez (en la primera figura): el archivo abre sin internet.
        div = fig.to_html(full_html=False, include_plotlyjs=primero, config={"displayModeBar": False, "responsive": True})
        primero = False
        bloques += (f"<details class='detalle'><summary>{esc(titulo)}</summary>{div}"
                    + "".join(f"<p class='chica'>{esc(t)}</p>" for t in pie) + "</details>")
    return bloques


CSS = f"""
body {{ background:{FONDO}; color:{TINTA}; font-family:{FUENTE}; margin:0; padding:28px 16px 48px; line-height:1.45; }}
main {{ max-width:1040px; margin:0 auto; }}
h1 {{ font-size:15px; font-weight:600; color:{TINTA_2}; margin:0 0 10px; letter-spacing:.02em; text-transform:uppercase; }}
h2 {{ font-size:20px; margin:44px 0 8px; }} h3 {{ font-size:16px; margin:0 0 6px; }}
h4 {{ font-size:12px; margin:0 0 4px; color:{TINTA_2}; text-transform:uppercase; letter-spacing:.04em; font-weight:600; }}
p {{ margin:0 0 10px; }} small, .chica {{ font-size:12.5px; color:{TINTA_2}; }}
.respuesta {{ font-size:26px; line-height:1.3; margin:0 0 10px; font-weight:400; }}
.foto {{ font-size:15px; }}
.grande {{ font-size:44px; font-weight:650; line-height:1.1; font-variant-numeric:tabular-nums; }} .rotulo {{ color:{TINTA_2}; font-size:14px; }}
.franja {{ display:grid; grid-template-columns:repeat(4, 1fr); gap:12px; margin:22px 0 12px; }}
.cifra {{ background:#fff; border:1px solid {BORDE}; border-top:4px solid {GRIS_CLARO}; border-radius:8px; padding:12px 16px; display:flex; flex-direction:column; }}
.cifra.mant, .tarjeta.propia {{ border-top-color:{NARANJA}; }} .cifra.umbral {{ border-top-color:{AZUL}; }} .cifra.sensor {{ border-top-color:{TINTA_2}; }}
.flota {{ display:flex; flex-wrap:wrap; gap:4px; margin:14px 0 6px; }}
.flota i, .leyenda i {{ width:20px; height:20px; border-radius:4px; display:inline-block; background:{GRIS_CLARO}; }}
i.mant {{ background:{NARANJA}; }} i.umbral {{ background:{AZUL}; }} i.sensor {{ background:{TINTA_2}; }}
.leyenda span {{ white-space:nowrap; margin-left:10px; }} .leyenda i {{ width:11px; height:11px; border-radius:3px; margin-right:5px; vertical-align:-1px; }}
.equipo {{ background:#fff; border:1px solid {BORDE}; border-left:6px solid {TINTA_2}; border-radius:8px; margin:14px 0; overflow:hidden; }}
.equipo.mant {{ border-left-color:{NARANJA}; }} .equipo.umbral {{ border-left-color:{AZUL}; }}
.equipo header {{ padding:14px 18px 12px; display:flex; flex-wrap:wrap; align-items:baseline; gap:4px 16px; background:#f3f2ee; }}
.equipo.mant header {{ background:#fdeee7; }} .equipo.umbral header {{ background:#e9f1fc; }}
.accion {{ font-size:22px; font-weight:650; line-height:1.2; }} .quien {{ font-size:15px; }}
.cuerpo {{ display:grid; grid-template-columns:1.2fr 1fr 1.2fr; gap:20px; padding:14px 18px 6px; }}
.cambio {{ display:flex; align-items:flex-end; gap:12px; }} .cambio span {{ display:flex; flex-direction:column; }}
.cambio b {{ font-size:20px; font-variant-numeric:tabular-nums; }} .cambio .flecha {{ color:{TINTA_2}; font-size:20px; }}
.nota {{ margin:0; padding:9px 18px; border-top:1px solid {BORDE}; font-size:13.5px; color:{TINTA_2}; }}
.veredicto {{ font-size:19px; line-height:1.35; margin-bottom:8px; }}
.tarjetas {{ display:grid; grid-template-columns:repeat(auto-fit, minmax(280px, 1fr)); gap:16px; margin:14px 0; }}
.tarjeta {{ background:#fff; border:1px solid {BORDE}; border-radius:8px; padding:16px 18px; border-top:4px solid {GRIS}; }}
.cifras {{ display:flex; gap:36px; flex-wrap:wrap; }} .cifras div {{ display:flex; flex-direction:column; }}
.precision {{ margin:12px 0 0; font-size:14px; color:{TINTA_2}; }}
table {{ width:100%; border-collapse:collapse; background:#fff; border:1px solid {BORDE}; font-size:15px; margin-top:8px; }}
th {{ text-align:left; font-size:12.5px; color:{TINTA_2}; font-weight:600; padding:10px 14px; border-bottom:1px solid {BORDE}; background:#f6f5f2; }}
td {{ padding:9px 14px; vertical-align:top; border-bottom:1px solid {BORDE}; }} tr:last-child td {{ border-bottom:0; }}
.si {{ font-weight:600; }} .no, .tarde {{ color:{TINTA_2}; }}
.detalle {{ border:1px solid {BORDE}; border-radius:8px; background:{FONDO}; margin:12px 0; padding:0 12px; }}
.detalle summary {{ cursor:pointer; font-weight:600; padding:14px 6px; }} .detalle[open] {{ padding-bottom:8px; }}
.detalle p {{ margin-left:8px; margin-right:8px; }}
.sin-grafico {{ border:1px dashed {BORDE}; border-radius:8px; padding:14px 18px; margin:12px 0; }}
.pie {{ border-top:1px solid {BORDE}; margin-top:40px; padding-top:12px; }}
@media (max-width:720px) {{
  .respuesta {{ font-size:21px; }} .franja {{ grid-template-columns:repeat(2, 1fr); }} .cuerpo {{ grid-template-columns:1fr; gap:6px; }}
  thead {{ display:none; }} td {{ display:block; border:0; padding:4px 14px; }} tr {{ display:block; border-bottom:1px solid {BORDE}; padding:8px 0; }}
  td::before {{ content:attr(data-t); display:block; font-size:11.5px; color:{TINTA_2}; text-transform:uppercase; letter-spacing:.03em; }}
}}
"""

# Los gráficos nacen dentro de un <details> cerrado: al abrirlo hay que avisarle a plotly que mida de nuevo.
# Con #detalle en la dirección, o al imprimir, se abren todos.
JS = """
const detalles = document.querySelectorAll('details.detalle');
const medir = d => d.querySelectorAll('.plotly-graph-div').forEach(g => window.Plotly && Plotly.Plots.resize(g));
detalles.forEach(d => d.addEventListener('toggle', () => d.open && medir(d)));
const abrir = () => detalles.forEach(d => { d.open = true; });
if (location.hash === '#detalle') abrir();
window.addEventListener('beforeprint', abrir);
"""


def main():
    lista, su, sin = leer("lista.csv"), leer("sobre-umbral.csv"), leer("sin-datos.csv")
    bt, fallas, episodios = leer("backtest.csv").set_index("combo_id"), leer("backtest-fallas.csv"), leer("backtest-episodios.csv")
    cfg = tomllib.loads((RAIZ / "config" / "backtest.toml").read_text())
    principal = next(c for c in cfg["combinaciones"] if c.get("principal"))
    pid, k = principal["id"], principal["k"]
    minimo, horizonte = cfg["evaluacion"]["anticipacion_minima_dias"], cfg["evaluacion"]["horizonte_dias"]
    p, fab = bt.loc[pid], bt.loc["FAB"]
    periodo = (f"{dia(fallas.fecha_falla.min())} al {dia(fallas.fecha_falla.max())}" if fallas.fecha_falla.notna().any()
               else "período (no hubo fallas)")

    con = duckdb.connect(str(SALIDA / "limpieza.duckdb"), read_only=True)
    cierre, total = con.execute("SELECT (SELECT max(ts) FROM lecturas), (SELECT count(*) FROM equipos)").fetchone()
    cierre = pd.Timestamp(cierre)
    # "La semana": los 7 días posteriores al último dato (asunción propia, a confirmar con el cliente).
    inicio = cierre.normalize() + pd.Timedelta(days=1)
    semana = f"{dia(inicio)} al {(inicio + pd.Timedelta(days=DIAS_SEMANA - 1)).strftime('%d/%m/%Y')}"
    notas_equipo = tomllib.loads(NOTAS.read_text(encoding="utf-8")).get("notas", {}) if NOTAS.is_file() else {}
    filas = armar_filas(con, lista, su, sin, p, pid, periodo, notas_equipo)
    franja = html_franja(con, lista, su, sin, total)
    detalle = html_detalle(con, filas, cierre, k)
    con.close()

    c = conteos(p)
    # Días con 7 de futuro completo = días de datos − ventana − horizonte: con drops cortos da 0 o negativo.
    dias_fa = int(p.dias_para_falsas_alarmas)
    if dias_fa > 0:
        frase_umbral = f" El umbral del fabricante solo habría dado unas {round(float(fab.falsas_alarmas_por_semana))} por semana."
        cuenta_fa = f"falsas alarmas contadas sobre {plural(dias_fa, 'día', 'días')}"
    else:
        frase_umbral = ""
        cuenta_fa = (f"las falsas alarmas todavía no se pueden contar: hacen falta al menos "
                     f"{cfg['normal']['dias_ventana'] + horizonte + 1} días de datos")
    pagina = f"""<!doctype html>
<html lang="es"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Mantenimiento del {semana}</title>
<style>{CSS}</style></head><body><main>
<h1>Mantenimiento · qué atender del {semana}</h1>
<p class="respuesta">{frase_respuesta(lista, su, sin, total, semana)}</p>
<p class="foto">Según lecturas hasta el {cierre.strftime('%d/%m/%Y')}, {cierre.strftime('%H:%M')}. Es una foto al cierre de los datos,
no una predicción para esa semana.</p>
{franja}

<h2>Qué hacer del {semana}</h2>
{html_tarjetas(filas, su, sin)}

<h2>¿Se puede confiar en el aviso de mantenimiento?</h2>
<p class="veredicto"><b>{esc(veredicto(p, fab))}</b></p>
<p>Con {c['n']} fallas la evidencia es modesta: el aviso no vio venir {c['n'] - c['a']} de las {c['n']}.</p>
<p>Esta prueba vale solo para la acción "Mandar a mantenimiento". El aviso de vibración alta todavía no tiene prueba propia.</p>
<div class="tarjetas">{tarjeta("Nuestro aviso de mantenimiento", pid, p, "propia", episodios, minimo, horizonte)}{tarjeta("Solo el umbral del fabricante", "FAB", fab, "fab", episodios, minimo, horizonte)}</div>
<p><b>Por qué importan las falsas alarmas:</b> cada una manda a un técnico a revisar un equipo que estaba bien, y una lista
que se equivoca seguido se deja de mirar.{frase_umbral}</p>
<p class="chica">Cómo se probó: con el historial, día por día y sin mirar el futuro. "Avisada" = con al menos {minimo} días de
anticipación. Fallas del {periodo}; {cuenta_fa}.</p>
{html_fallas(fallas, pid)}

<h2>Detalle por equipo</h2>
<p>Cómo leerlo: la línea azul es la vibración típica de cada día. Si sube día tras día, el equipo se está deteriorando;
las líneas punteadas son referencias.</p>
{detalle}

<p class="chica pie">{esc(pid)}: avisa cuando una señal supera {num(k, 1)} veces el nivel habitual del
equipo (mediana de sus {cfg['normal']['dias_ventana']} días previos) durante {principal['lecturas']} lecturas seguidas. SU: avisa cuando la mediana diaria de
vibración pasa el umbral del fabricante varios días seguidos; se agregó después de ver los datos, por eso todavía no tiene
evidencia propia. "Vibración típica del día" = mediana diaria. Generado por el pipeline (make run); las cifras salen de lista.csv,
sobre-umbral.csv, sin-datos.csv, backtest.csv, backtest-fallas.csv, backtest-episodios.csv y limpieza.duckdb.</p>
</main><script>{JS}</script></body></html>"""
    (SALIDA / "dashboard.html").write_text(pagina, encoding="utf-8")
    print(f"OK: salida/dashboard.html ({len(filas)} equipos, semana del {semana})")

    # Chequeo [AUTO] de SPEC R8: autocontenido, cada equipo de la lista, recall y precisión iguales a backtest.csv.
    spec = importlib.util.spec_from_file_location("r8", RAIZ / "tests" / "dashboard" / "r8.py")
    r8 = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(r8)
    problemas = r8.revisar(SALIDA)
    print(f"[{'fallo' if problemas else 'ok':>5}] tests/dashboard/r8.py")
    if problemas:
        sys.exit("Dashboard cortado (R8):\n  " + "\n  ".join(problemas))


if __name__ == "__main__":
    main()
