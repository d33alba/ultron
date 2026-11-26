"""Presentaciones en Markdown: análisis, reparto de tiempo, render con Rich y exportación HTML."""

from __future__ import annotations

import html
import re
from dataclasses import dataclass, field
from pathlib import Path

from rich.console import Group, RenderableType
from rich.markdown import Markdown
from rich.syntax import Syntax
from rich.text import Text

from ultron.modos.presentacion import letras


@dataclass
class Bloque:
    tipo: str          # vineta | codigo | texto
    contenido: str
    lenguaje: str = ""


@dataclass
class Diapo:
    titulo: str = ""
    bloques: list[Bloque] = field(default_factory=list)
    notas: str = ""

    @property
    def pasos(self) -> int:
        """Cuántas pulsaciones necesita: una por viñeta (mínimo 1)."""
        return max(1, sum(b.tipo == "vineta" for b in self.bloques))

    def palabras(self) -> int:
        return len((self.titulo + " " + " ".join(b.contenido for b in self.bloques)).split())


def _cerrar(d: Diapo, parrafo: list[str]) -> None:
    if parrafo:
        d.bloques.append(Bloque("texto", "\n".join(parrafo).strip()))
        parrafo.clear()


def analizar(texto: str) -> list[Diapo]:
    diapos = []
    for trozo in re.split(r"(?m)^---\s*$", texto):
        if not trozo.strip():
            continue
        partes = re.split(r"(?m)^\?\?\?\s*$", trozo, maxsplit=1)
        cuerpo, notas = partes[0], (partes[1].strip() if len(partes) > 1 else "")
        d = Diapo(notas=notas)
        lineas = cuerpo.strip("\n").splitlines()
        i = 0
        parrafo: list[str] = []
        while i < len(lineas):
            linea = lineas[i]
            if linea.startswith("```"):
                _cerrar(d, parrafo)
                lenguaje = linea[3:].strip()
                codigo = []
                i += 1
                while i < len(lineas) and not lineas[i].startswith("```"):
                    codigo.append(lineas[i])
                    i += 1
                d.bloques.append(Bloque("codigo", "\n".join(codigo), lenguaje or "text"))
            elif re.match(r"^#{1,2}\s+", linea) and not d.titulo:
                d.titulo = re.sub(r"^#{1,2}\s+", "", linea).strip()
            elif re.match(r"^\s*[-*]\s+", linea):
                _cerrar(d, parrafo)
                d.bloques.append(Bloque("vineta", re.sub(r"^\s*[-*]\s+", "", linea)))
            elif linea.strip():
                parrafo.append(linea)
            else:
                _cerrar(d, parrafo)
            i += 1
        _cerrar(d, parrafo)
        diapos.append(d)
    return diapos


def repartir_tiempo(diapos: list[Diapo], minutos: float) -> list[float]:
    """Minutos por diapositiva, proporcionales a su contenido (mínimo 0,25 min)."""
    if not diapos:
        return []
    pesos = [max(5, d.palabras()) + 15 * sum(b.tipo == "codigo" for b in d.bloques)
             for d in diapos]
    total = sum(pesos)
    tiempos = [max(0.25, minutos * p / total) for p in pesos]
    escala = minutos / sum(tiempos)
    return [round(x * escala, 2) for x in tiempos]


def render(d: Diapo, paso: int, ancho: int, estilos: dict[str, str]) -> RenderableType:
    """La diapositiva con las viñetas reveladas hasta `paso` (0 = solo la primera)."""
    partes: list[RenderableType] = []
    if d.titulo:
        if letras.ancho(d.titulo) <= ancho - 4:
            for fila in letras.grandes(d.titulo):
                partes.append(Text(fila, style=estilos.get("titulo", "bold")))
        else:
            partes.append(Text(d.titulo, style=estilos.get("titulo", "bold")))
        partes.append(Text(""))
    vinetas_vistas = 0
    for b in d.bloques:
        if b.tipo == "vineta":
            if vinetas_vistas > paso:
                continue
            vinetas_vistas += 1
            linea = Text("  ◆ ", style=estilos.get("vineta", ""))
            linea.append_text(Text.from_markup(_markdown_simple(b.contenido)))
            partes.append(linea)
        elif b.tipo == "codigo":
            partes.append(Syntax(b.contenido, b.lenguaje, theme="monokai", padding=1))
        else:
            partes.append(Markdown(b.contenido))
    return Group(*partes)


def _markdown_simple(texto: str) -> str:
    texto = texto.replace("[", r"\[")
    texto = re.sub(r"\*\*(.+?)\*\*", r"[bold]\1[/bold]", texto)
    texto = re.sub(r"\*(.+?)\*", r"[italic]\1[/italic]", texto)
    return re.sub(r"`(.+?)`", r"[reverse]\1[/reverse]", texto)


def a_html(diapos: list[Diapo], titulo: str, paleta: dict[str, str]) -> str:
    """HTML autocontenido con navegación por teclado."""
    secciones = []
    for d in diapos:
        cuerpo = []
        for b in d.bloques:
            if b.tipo == "vineta":
                cuerpo.append(f"<li>{html.escape(b.contenido)}</li>")
            elif b.tipo == "codigo":
                cuerpo.append(f"<pre><code>{html.escape(b.contenido)}</code></pre>")
            else:
                cuerpo.append(f"<p>{html.escape(b.contenido)}</p>")
        contenido = "".join(cuerpo).replace("</li><li>", "</li><li>")
        contenido = re.sub(r"((?:<li>.*?</li>)+)", r"<ul>\1</ul>", contenido)
        secciones.append(f"<section><h1>{html.escape(d.titulo)}</h1>{contenido}"
                         f"<aside>{html.escape(d.notas)}</aside></section>")
    fondo, texto = paleta.get("fondo", "#2B2B2E"), paleta.get("texto", "#ffffff")
    acento = paleta.get("acento", "#F2C14E")
    return f"""<!doctype html><html lang="es"><meta charset="utf-8"><title>{html.escape(titulo)}</title>
<style>body{{margin:0;background:{fondo};color:{texto};font:28px/1.5 system-ui,sans-serif}}
section{{display:none;height:100vh;box-sizing:border-box;padding:8vh 10vw}}
section.activa{{display:block}}h1{{color:{acento};font-size:2.4em;margin:0 0 .6em}}
li::marker{{color:{acento}}}pre{{background:#0006;padding:1em;border-radius:8px;font-size:.7em}}
aside{{display:none}}#n{{position:fixed;bottom:16px;right:24px;opacity:.6;font-size:18px}}</style>
{''.join(secciones)}<div id="n"></div><script>
const s=[...document.querySelectorAll('section')];let i=0;
function ver(){{s.forEach((x,k)=>x.classList.toggle('activa',k===i));
document.getElementById('n').textContent=(i+1)+' / '+s.length}}
addEventListener('keydown',e=>{{if(['ArrowRight',' ','PageDown'].includes(e.key))i=Math.min(i+1,s.length-1);
if(['ArrowLeft','PageUp'].includes(e.key))i=Math.max(i-1,0);ver()}});ver();</script></html>"""


def cargar(archivo: Path) -> list[Diapo]:
    return analizar(Path(archivo).read_text(encoding="utf-8"))
