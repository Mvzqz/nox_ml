"""Build the course PDFs (Markdown -> HTML -> PDF with WeasyPrint).

Usage (from the repository root):

    uv run --with weasyprint --with markdown docs/entregables/build_pdf.py            # both
    uv run --with weasyprint --with markdown docs/entregables/build_pdf.py Avance0.39  # one

Each Markdown file starts with a front matter block (``key: value`` lines between
``---``) holding the cover title. The cover, the table of contents (with page
numbers resolved by CSS ``target-counter``) and the page numbers are added here.
Captions are plain paragraphs that start with "Tabla N." or "Figura N."; the
script checks that each kind is numbered consecutively.
"""

from __future__ import annotations

import html
import re
import sys
from pathlib import Path

import markdown
from weasyprint import HTML

HERE = Path(__file__).resolve().parent
DOCS = ["Planteamiento.39", "Avance0.39"]
DATE = "25 de octubre de 2026"
STUDENTS = [
    ("Isabella Arango Restrepo", "A01796305"),
    ("Manuel Alejandro Vázquez Meza", "A01796404"),
    ("Isaí Ambrocio", "A01625101"),
]
PROFESSORS = ["Juan Arturo Nolazco Flores", "Guillermo Mota Medina"]

CSS = """
@page { size: A4; margin: 2.5cm 2.5cm 2.5cm 2.5cm;
  @bottom-center { content: counter(page); font: 10pt 'Times New Roman', Times, serif; } }
@page cover { margin: 2.5cm; @bottom-center { content: none; } }
html { font: 11.5pt/1.4 'Times New Roman', 'Liberation Serif', Times, serif; }
body { text-align: justify; hyphens: auto; }
h1, h2, h3 { font-family: 'Times New Roman', 'Liberation Serif', Times, serif; text-align: left;
  hyphens: manual; break-after: avoid; color: #0b2a6b; }
h1 { font-size: 16pt; margin: 1.4em 0 0.5em; }
h2 { font-size: 13pt; margin: 1.1em 0 0.4em; }
h3 { font-size: 11.5pt; margin: 0.9em 0 0.3em; }
h1.pb { break-before: page; margin-top: 0; }
p { margin: 0 0 0.6em; orphans: 3; widows: 3; }
ul, ol { margin: 0 0 0.6em 0; padding-left: 1.4em; }
li { margin-bottom: 0.2em; }
a { color: inherit; text-decoration: none; }
code { font-family: 'DejaVu Sans Mono', monospace; font-size: 9pt; }
table { border-collapse: collapse; width: 100%; margin: 0 0 1em; font-size: 9.5pt;
  text-align: left; hyphens: manual; }
th, td { border: 0.6pt solid #666; padding: 3pt 5pt; vertical-align: top; }
th { background: #e6ebf5; }
thead { display: table-header-group; }
tr { break-inside: avoid; }
p.caption { font-size: 10pt; text-align: left; margin: 1em 0 0.3em; font-weight: bold;
  break-after: avoid; }
p.caption.figura { text-align: center; break-after: auto; margin-top: 0.3em; break-before: avoid; }
figure { margin: 1em 0 0; text-align: center; break-inside: avoid; }
figure img { max-width: 100%; }
.cover { page: cover; text-align: center; break-after: page; }
.cover img { width: 11.5cm; margin: 0.5cm 0 3.2cm; }
.cover .course { font-weight: bold; font-size: 12pt; margin-bottom: 2.6cm; }
.cover .title { font-weight: bold; font-size: 17pt; margin-bottom: 0.3cm; }
.cover .subtitle { font-style: italic; font-size: 11.5pt; margin: 0 1.5cm 2.2cm; }
.cover .label { font-weight: bold; margin: 1.2cm 0 0.4cm; }
.cover table.people { border: none; width: auto; margin: 0 auto; font-size: 11.5pt; }
.cover table.people td { border: none; padding: 1pt 8pt; text-align: left; }
.cover .date { margin-top: 2.2cm; }
.toc-title { font-size: 16pt; font-weight: bold; color: #0b2a6b; margin-bottom: 0.8em;
  break-after: avoid; }
.toc { break-after: page; }
.toc a { display: block; text-align: left; margin-bottom: 0.25em; }
.toc a.l2 { margin-left: 1.4em; font-size: 10.5pt; }
.toc a.l1 { margin-top: 0.5em; font-weight: bold; }
.toc a::after { content: leader('.') target-counter(attr(href), page); font-weight: normal; }
.refs p { padding-left: 1.5em; text-indent: -1.5em; text-align: left; }
"""


def parse(src: str) -> tuple[dict[str, str], str]:
    m = re.match(r"---\n(.*?)\n---\n", src, re.S)
    meta = {}
    for line in m.group(1).splitlines():
        k, v = line.split(":", 1)
        meta[k.strip()] = v.strip()
    return meta, src[m.end() :]


def cover(meta: dict[str, str]) -> str:
    rows = "".join(f"<tr><td>{n}</td><td>-</td><td>{i}</td></tr>" for n, i in STUDENTS)
    profs = "".join(f"<p>{p}</p>" for p in PROFESSORS)
    sub = f'<div class="subtitle">{meta["subtitle"]}</div>' if "subtitle" in meta else ""
    return (
        '<section class="cover">'
        '<img src="assets/tec_logo.png" alt="Tecnológico de Monterrey">'
        '<div class="course">Proyecto Integrador (Gpo 10)</div>'
        f'<div class="title">{meta["title"]}</div>{sub}'
        '<div class="label">Estudiantes:</div>'
        f'<table class="people">{rows}</table>'
        '<div class="label">Profesores:</div>'
        f"{profs}"
        f'<div class="date">{DATE}</div>'
        "</section>"
    )


def build(name: str) -> None:
    src = (HERE / f"{name}.md").read_text(encoding="utf-8")
    meta, body = parse(src)
    md = markdown.Markdown(
        extensions=["tables", "attr_list", "md_in_html", "toc"],
        extension_configs={"toc": {"permalink": False}},
    )
    content = md.convert(body)

    # Captions and numbering check.
    counts = {"Tabla": 0, "Figura": 0}

    def caption(m: re.Match[str]) -> str:
        kind, num = m.group(1), int(m.group(2))
        counts[kind] += 1
        if num != counts[kind]:
            raise SystemExit(f"{name}: {kind} {num} out of order (expected {counts[kind]})")
        cls = "figura" if kind == "Figura" else "tabla"
        return f'<p class="caption {cls}">{kind} {num}.'

    content = re.sub(r"<p>(Tabla|Figura) (\d+)\.", caption, content)
    # Every table must follow a caption.
    n_tables = content.count("<table>")
    if n_tables != counts["Tabla"]:
        raise SystemExit(f"{name}: {n_tables} tables but {counts['Tabla']} table captions")

    content = content.replace("<h1 ", '<h1 class="pb" ', 1)

    # Table of contents from h1/h2.
    entries = []
    for m in re.finditer(r'<h([12])[^>]*? id="([^"]+)"[^>]*>(.*?)</h\1>', content):
        lvl, hid, text = m.groups()
        text = re.sub(r"<[^>]+>", "", text)
        entries.append(f'<a class="l{lvl}" href="#{hid}">{text}</a>')
    toc = '<section class="toc"><div class="toc-title">Índice</div>' + "".join(entries) + "</section>"

    # Wrap the bibliography.
    content = re.sub(
        r'(<h1 [^>]*id="bibliograf[^"]*"[^>]*>.*?</h1>)(.*)$',
        r'\1<div class="refs">\2</div>',
        content,
        flags=re.S,
    )

    doc = (
        f'<!doctype html><html lang="es"><head><meta charset="utf-8">'
        f"<title>{html.escape(meta['title'])}</title><style>{CSS}</style></head><body>"
        f"{cover(meta)}{toc}{content}</body></html>"
    )
    out_html = HERE / f"{name}.html"
    out_html.write_text(doc, encoding="utf-8")
    HTML(string=doc, base_url=str(HERE)).write_pdf(HERE / f"{name}.pdf")
    out_html.unlink()
    print(f"{name}.pdf ok ({counts['Tabla']} tablas, {counts['Figura']} figuras)")


if __name__ == "__main__":
    for n in sys.argv[1:] or DOCS:
        build(n)
