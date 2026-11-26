"""Extracción de texto de PDF (con OCR si hace falta), txt, md y docx, por páginas."""

from __future__ import annotations

import re
import tempfile
import zipfile
from html import unescape
from pathlib import Path

from ultron.nucleo.ejecutor import Ejecutor

Paginas = list[tuple[int, str]]
FORMATOS = (".pdf", ".txt", ".md", ".docx")


class ErrorExtraccion(Exception):
    """No se ha podido leer el documento."""


def extraer(archivo: Path, ej: Ejecutor | None = None) -> Paginas:
    archivo = Path(archivo)
    if not archivo.exists():
        raise ErrorExtraccion(f"No existe {archivo}.")
    sufijo = archivo.suffix.lower()
    if sufijo == ".pdf":
        return _pdf(archivo, ej or Ejecutor())
    if sufijo in (".txt", ".md"):
        return [(1, archivo.read_text(encoding="utf-8", errors="ignore"))]
    if sufijo == ".docx":
        return [(1, _docx(archivo))]
    raise ErrorExtraccion(f"Formato no soportado: {sufijo}. Usa {', '.join(FORMATOS)}.")


def _pdf(archivo: Path, ej: Ejecutor) -> Paginas:
    from pypdf import PdfReader
    from pypdf.errors import PdfReadError

    try:
        lector = PdfReader(str(archivo))
        paginas = [(i, p.extract_text() or "") for i, p in enumerate(lector.pages, 1)]
    except (PdfReadError, OSError, ValueError) as e:
        raise ErrorExtraccion(f"No puedo leer el PDF: {e}") from e
    salida: Paginas = []
    for numero, texto in paginas:
        if len(texto.strip()) < 30:
            texto = _pdftotext(archivo, numero, ej) or texto
        if len(texto.strip()) < 30:
            texto = _ocr(archivo, numero, ej) or texto
        salida.append((numero, texto))
    return salida


def _pdftotext(archivo: Path, pagina: int, ej: Ejecutor) -> str:
    if not ej.existe("pdftotext"):
        return ""
    r = ej.leer(["pdftotext", "-layout", "-f", str(pagina), "-l", str(pagina), str(archivo), "-"])
    return r.salida if r.codigo == 0 else ""


def _ocr(archivo: Path, pagina: int, ej: Ejecutor) -> str:
    if not (ej.existe("tesseract") and ej.existe("pdftoppm")):
        return ""
    with tempfile.TemporaryDirectory() as tmp:
        prefijo = Path(tmp) / "p"
        ej.leer(["pdftoppm", "-f", str(pagina), "-l", str(pagina), "-r", "200", "-png",
                 str(archivo), str(prefijo)], timeout=120)
        imagenes = sorted(Path(tmp).glob("p*.png"))
        if not imagenes:
            return ""
        r = ej.leer(["tesseract", str(imagenes[0]), "-", "-l", "spa+eng"], timeout=180)
        return r.salida if r.codigo == 0 else ""


def _docx(archivo: Path) -> str:
    try:
        with zipfile.ZipFile(archivo) as z:
            xml = z.read("word/document.xml").decode("utf-8", errors="ignore")
    except (zipfile.BadZipFile, KeyError) as e:
        raise ErrorExtraccion("El .docx está dañado.") from e
    parrafos = []
    for p in re.findall(r"<w:p[ >].*?</w:p>", xml, re.S):
        texto = "".join(re.findall(r"<w:t[^>]*>(.*?)</w:t>", p, re.S))
        if texto.strip():
            parrafos.append(unescape(texto))
    return "\n\n".join(parrafos)


def texto_con_paginas(paginas: Paginas) -> str:
    return "\n\n".join(f"[p. {n}]\n{t.strip()}" for n, t in paginas if t.strip())


def texto_plano(paginas: Paginas) -> str:
    return "\n\n".join(t.strip() for _, t in paginas if t.strip())
