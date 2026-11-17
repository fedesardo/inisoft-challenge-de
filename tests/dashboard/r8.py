"""Chequeo [AUTO] de SPEC R8 sobre salida/dashboard.html. Devuelve la lista de problemas (vacía = pasa).

  uv run --locked python tests/dashboard/r8.py      # código 1 si hay problemas

(1) Autocontenido: ningún recurso que el navegador descargue de la red. Se miran las etiquetas que cargan
    algo (script, img, iframe, etc. con src; link con href) y el CSS (url(http…) y @import). No se mira el
    texto dentro de los <script>: plotly.js embebido trae enlaces de texto (href="https://plotly.com/") que
    no descargan nada.
(2) Contiene cada equipo de lista.csv.
(3) Recall y precisión de las tarjetas (atributos data-*) idénticos a backtest.csv (D-34):
    recall = fallas anticipadas / fallas evaluables; precisión = avisos acertados / avisos ya juzgables,
    con acierto = falla dentro de los 7 días, incluso el mismo día. También las falsas alarmas, los avisos
    muy recientes y el desglose de los aciertos (a tiempo / tarde) contra backtest-episodios.csv, y que cada
    cifra del desglose figure en el texto visible de la tarjeta.
"""
import csv
import re
import sys
from html.parser import HTMLParser
from pathlib import Path

SALIDA = Path(__file__).resolve().parents[2] / "salida"
REMOTO = re.compile(r"^\s*(https?:)?//", re.I)
CSS_REMOTO = re.compile(r"url\(\s*['\"]?\s*(https?:)?//|@import", re.I)


class Lector(HTMLParser):
    def __init__(self):
        super().__init__()
        self.problemas, self.tarjetas, self.en_style = [], {}, False
        self.regla, self.en_precision = None, False

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        self.en_style = tag == "style"
        carga = a.get("href") if tag == "link" else a.get("src") if tag != "a" else None
        if carga and REMOTO.match(carga):
            self.problemas.append(f"recurso externo: <{tag}> carga {carga[:80]}")
        if a.get("style") and CSS_REMOTO.search(a["style"]):
            self.problemas.append(f"recurso externo en style de <{tag}>")
        if "data-regla" in a:
            self.regla = a["data-regla"]
            self.tarjetas[self.regla] = {k[5:]: v for k, v in a.items() if k.startswith("data-")} | {"texto": ""}
        self.en_precision = tag == "p" and a.get("class") == "precision"

    def handle_endtag(self, tag):
        self.en_style = self.en_precision = False

    def handle_data(self, data):
        if self.en_precision and self.regla:
            self.tarjetas[self.regla]["texto"] += data
        if self.en_style and CSS_REMOTO.search(data):
            self.problemas.append("recurso externo en <style>: url(http…) o @import")


def revisar(salida=SALIDA):
    pagina = (salida / "dashboard.html").read_text(encoding="utf-8")
    lector = Lector()
    lector.feed(pagina)
    problemas = lector.problemas
    with (salida / "lista.csv").open() as f:
        problemas += [f"falta el equipo {r['equipo']} de lista.csv" for r in csv.DictReader(f) if r["equipo"] not in pagina]
    with (salida / "backtest.csv").open() as f:
        bt = {r["combo_id"]: r for r in csv.DictReader(f)}
    if not lector.tarjetas:
        problemas.append("no hay tarjetas con data-regla: no se puede comparar recall ni precisión")
    with (salida / "backtest-episodios.csv").open() as f:
        episodios = list(csv.DictReader(f))
    for regla, t in lector.tarjetas.items():
        r = bt[regla]
        juzgables = int(r["episodios"]) - int(r["episodios_sin_evaluar"])
        acertados = juzgables - int(r["falsas_alarmas"])
        clases = [e["clase"] for e in episodios if e["combo_id"] == regla]
        esperado = {"recall": f"{r['fallas_anticipadas_2d']}/{r['fallas_evaluables']}", "precision": f"{acertados}/{juzgables}",
                    "falsas": r["falsas_alarmas"], "recientes": r["episodios_sin_evaluar"],
                    "a-tiempo": str(clases.count("acierto_2_7")), "tarde": str(clases.count("acierto_0_1"))}
        for campo, valor in esperado.items():
            if t.get(campo) != valor:
                problemas.append(f"{regla}: el dashboard dice {campo} = {t.get(campo)}; los CSV dan {valor}")
        if clases.count("acierto_2_7") + clases.count("acierto_0_1") != acertados:
            problemas.append(f"{regla}: los aciertos de backtest-episodios.csv no suman los {acertados} derivados de backtest.csv")
        # Las cifras tienen que estar también en el texto que lee la jefa, no solo en los atributos.
        cifras = set(re.findall(r"\d+", t["texto"]))
        for nombre, n in (("avisos", int(r["episodios"])), ("juzgables", juzgables), ("falsas alarmas", int(r["falsas_alarmas"])),
                          ("muy recientes", int(r["episodios_sin_evaluar"]))):
            if n > 1 and str(n) not in cifras:
                problemas.append(f"{regla}: el texto de precisión no menciona {n} ({nombre})")
    return problemas


if __name__ == "__main__":
    problemas = revisar()
    print("\n".join(problemas) or "OK: dashboard autocontenido, con cada equipo de la lista y recall y precisión iguales a backtest.csv y backtest-episodios.csv")
    sys.exit(1 if problemas else 0)
