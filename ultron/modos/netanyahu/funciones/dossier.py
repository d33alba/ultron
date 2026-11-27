"""Dossier de operación: HTML con estética de unidad de inteligencia (y PDF si hay Chromium)."""

from __future__ import annotations

import html
import json
import shutil
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any

CSS = """
*{box-sizing:border-box}body{margin:0;background:#06102a;color:#e8eeff;
font:15px/1.55 'Inter','Segoe UI',system-ui,sans-serif}
.banda{background:#0038B8;color:#fff;text-align:center;letter-spacing:.4em;font-weight:800;
padding:6px;font-size:12px}
header{padding:48px 56px 28px;border-bottom:2px solid #0038B8;
background:radial-gradient(circle at 85% 20%,#173682 0,#06102a 60%)}
.marca{color:#6EA8FE;letter-spacing:.35em;font-size:12px;font-weight:700}
h1{font-size:40px;margin:10px 0 6px;letter-spacing:.04em}
.sub{color:#8A94A6}.meta{display:flex;gap:28px;margin-top:20px;flex-wrap:wrap}
.meta div{background:#0d204e;border:1px solid #173682;border-radius:10px;padding:10px 16px}
.meta b{display:block;font-size:11px;color:#6EA8FE;letter-spacing:.2em}
main{padding:28px 56px 60px;display:grid;gap:22px}
section{background:#0a1a3f;border:1px solid #173682;border-radius:14px;padding:22px 26px}
h2{margin:0 0 14px;font-size:15px;letter-spacing:.25em;color:#6EA8FE}
.puntos{display:flex;align-items:center;gap:26px}
.anillo{width:130px;height:130px;border-radius:50%;display:grid;place-items:center;
font-size:38px;font-weight:800}
.anillo span{background:#0a1a3f;width:100px;height:100px;border-radius:50%;display:grid;
place-items:center}
ul{margin:0;padding-left:20px}li{margin:4px 0}
.alto{color:#ff6b7a}.medio{color:#ffd166}.bajo{color:#8ec5ff}
table{width:100%;border-collapse:collapse;font-size:13px}
td,th{border-bottom:1px solid #173682;padding:6px 8px;text-align:left;vertical-align:top}
th{color:#6EA8FE;font-weight:600;width:28%}
pre{white-space:pre-wrap;word-break:break-word;margin:0;font:12px/1.45 'JetBrains Mono',monospace;
color:#c9d6ff}
a{color:#8ec5ff}footer{color:#536484;text-align:center;font-size:12px;padding:0 0 40px}
@media print{body{background:#fff;color:#111}section,header{background:#fff!important;
color:#111}h2,.marca{color:#0038B8}}
"""


def _valor(v: Any) -> str:
    if isinstance(v, str):
        if v.startswith("http"):
            return f'<a href="{html.escape(v)}">{html.escape(v)}</a>'
        return html.escape(v)
    if isinstance(v, list) and all(isinstance(x, str) for x in v):
        return "<br>".join(_valor(x) for x in v[:60]) or "—"
    return f"<pre>{html.escape(json.dumps(v, ensure_ascii=False, indent=2)[:6000])}</pre>"


def _tabla(datos: dict) -> str:
    filas = "".join(f"<tr><th>{html.escape(str(k))}</th><td>{_valor(v)}</td></tr>"
                    for k, v in datos.items() if v not in (None, "", [], {}))
    return f"<table>{filas}</table>"


def generar(destino: Path, *, titulo: str, objetivo: str, tipo: str, puntuacion: int,
            hallazgos: list[tuple[str, str]], recomendaciones: list[str],
            secciones: dict[str, dict], extra_meta: dict[str, str] | None = None) -> Path:
    """Escribe el dossier HTML y devuelve su ruta."""
    color = "#E63946" if puntuacion >= 60 else ("#FFD166" if puntuacion >= 30 else "#4CD964")
    meta = {"OBJETIVO": objetivo, "TIPO": tipo,
            "FECHA": datetime.now().strftime("%d/%m/%Y %H:%M"), **(extra_meta or {})}
    cajas = "".join(f"<div><b>{html.escape(k)}</b>{html.escape(str(v))}</div>"
                    for k, v in meta.items())
    lista = "".join(f'<li class="{n}">{html.escape(t)}</li>' for n, t in hallazgos) \
        or "<li>Sin hallazgos relevantes.</li>"
    recs = "".join(f"<li>{html.escape(r)}</li>" for r in recomendaciones)
    cuerpo = "".join(f"<section><h2>{html.escape(n.upper())}</h2>{_tabla(d)}</section>"
                     for n, d in secciones.items() if isinstance(d, dict) and d)
    documento = f"""<!doctype html><html lang="es"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{html.escape(titulo)} · {html.escape(objetivo)}</title><style>{CSS}</style></head><body>
<div class="banda">CONFIDENCIAL · ULTRON · UNIDAD DE INTELIGENCIA</div>
<header><div class="marca">✡ ULTRON · NETANYAHU</div><h1>{html.escape(titulo)}</h1>
<div class="sub">Informe generado a partir de fuentes abiertas</div><div class="meta">{cajas}</div>
</header><main>
<section><h2>NIVEL DE EXPOSICIÓN</h2><div class="puntos">
<div class="anillo" style="background:conic-gradient({color} {puntuacion}%,#173682 0)">
<span>{puntuacion}</span></div><ul>{lista}</ul></div></section>
<section><h2>RECOMENDACIONES</h2><ul>{recs}</ul></section>
{cuerpo}</main><footer>Ultron · fuentes abiertas · {meta['FECHA']}</footer></body></html>"""
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(documento, encoding="utf-8")
    return destino


def a_pdf(html_ruta: Path) -> Path | None:
    """PDF con el Chromium/Chrome/Edge instalado (sin cabeceras del navegador)."""
    for nav in ("chromium", "chromium-browser", "google-chrome", "microsoft-edge", "msedge"):
        exe = shutil.which(nav)
        if not exe:
            continue
        pdf = html_ruta.with_suffix(".pdf")
        try:
            subprocess.run([exe, "--headless=new", "--disable-gpu", "--no-pdf-header-footer",
                            f"--print-to-pdf={pdf}", html_ruta.resolve().as_uri()],
                           capture_output=True, timeout=90, check=False)
        except (OSError, subprocess.SubprocessError):
            continue
        if pdf.exists():
            return pdf
    return None
