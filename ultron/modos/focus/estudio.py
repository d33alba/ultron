"""Lógica de estudio con IA: resúmenes, tarjetas, exámenes, preguntas, esquemas."""

from __future__ import annotations

import difflib
import hashlib
import json
from pathlib import Path
from typing import Any

from ultron.ia import util
from ultron.ia.cliente import preguntar
from ultron.modos.focus import bm25, datos, extraer

NIVELES_RESUMEN = {
    "corto": "Resume el texto en 3 a 5 líneas, con lo esencial.",
    "medio": "Resume el texto en varios párrafos claros, conservando las ideas principales.",
    "esquema": ("Haz un esquema de estudio en Markdown: títulos (##), viñetas y los conceptos "
                "clave en **negrita**. Incluye definiciones breves."),
}


def _clave(*partes: Any) -> str:
    return hashlib.sha256(json.dumps(partes, ensure_ascii=False).encode()).hexdigest()[:24]


def _cacheado(clave: str, calcular) -> Any:
    previo = datos.cache_leer(clave)
    if previo is not None:
        return json.loads(previo)
    valor = calcular()
    datos.cache_guardar(clave, json.dumps(valor, ensure_ascii=False))
    return valor


def cargar(archivo: Path) -> tuple[str, extraer.Paginas]:
    paginas = extraer.extraer(archivo)
    if not extraer.texto_plano(paginas).strip():
        raise extraer.ErrorExtraccion(
            "El documento no tiene texto (¿es un escaneo? instala tesseract-ocr-spa).")
    return datos.hash_archivo(archivo), paginas


# --- resumen -----------------------------------------------------------------------


def resumen(archivo: Path, nivel: str = "medio") -> str:
    h, paginas = cargar(archivo)
    instruccion = NIVELES_RESUMEN.get(nivel, NIVELES_RESUMEN["medio"])
    return _cacheado(_clave("resumen", h, nivel), lambda: util.resumir_largo(
        extraer.texto_plano(paginas), instruccion))


# --- flashcards ----------------------------------------------------------------------

EJEMPLO_TARJETAS = {"tarjetas": [{"pregunta": "¿Qué es…?", "respuesta": "Es…", "pagina": 1}]}


def _lista_tarjetas(respuesta: Any) -> list[dict]:
    if isinstance(respuesta, dict):
        respuesta = respuesta.get("tarjetas") or respuesta.get("flashcards") or []
    salida = []
    for t in respuesta if isinstance(respuesta, list) else []:
        if isinstance(t, dict) and t.get("pregunta") and t.get("respuesta"):
            salida.append({"pregunta": str(t["pregunta"]).strip(),
                           "respuesta": str(t["respuesta"]).strip(),
                           "pagina": t.get("pagina")})
    return salida


def deduplicar(tarjetas: list[dict], umbral: float = 0.85) -> list[dict]:
    unicas: list[dict] = []
    for t in tarjetas:
        if all(difflib.SequenceMatcher(None, t["pregunta"].lower(), u["pregunta"].lower()).ratio()
               < umbral for u in unicas):
            unicas.append(t)
    return unicas


def generar_tarjetas(archivo: Path, n: int = 20) -> list[dict]:
    h, paginas = cargar(archivo)

    def calcular() -> list[dict]:
        trozos = util.trocear(extraer.texto_con_paginas(paginas), max_chars=4000)
        por_trozo = max(2, -(-n // max(1, len(trozos))))
        todas: list[dict] = []
        for trozo in trozos:
            respuesta = util.pedir_json(
                f"Crea {por_trozo} tarjetas de estudio (pregunta corta y respuesta breve) a "
                "partir de este fragmento. Indica la página (marcas [p. N]).\n\n" + trozo,
                EJEMPLO_TARJETAS)
            todas += _lista_tarjetas(respuesta)
            if len(todas) >= n * 1.3:
                break
        return deduplicar(todas)[:n]

    return _cacheado(_clave("tarjetas", h, n), calcular)


def guardar_tarjetas(mazo: str, tarjetas: list[dict]) -> int:
    with datos.conectar() as con:
        for t in tarjetas:
            con.execute(
                "insert into tarjetas(mazo, pregunta, respuesta, pagina, creado) "
                "values (?, ?, ?, ?, ?)",
                (mazo, t["pregunta"], t["respuesta"], t.get("pagina"), datos.ahora()))
    return len(tarjetas)


def exportar_anki(mazo: str, tarjetas: list[dict], salida: Path) -> Path:
    import genanki

    id_modelo = int(hashlib.md5(b"ultron-basico").hexdigest()[:8], 16)
    id_mazo = int(hashlib.md5(mazo.encode()).hexdigest()[:8], 16)
    modelo = genanki.Model(
        id_modelo, "Ultron básico",
        fields=[{"name": "Pregunta"}, {"name": "Respuesta"}, {"name": "Pagina"}],
        templates=[{"name": "Tarjeta", "qfmt": "{{Pregunta}}",
                    "afmt": "{{FrontSide}}<hr id=answer>{{Respuesta}}"
                            "<br><small>p. {{Pagina}}</small>"}],
    )
    baraja = genanki.Deck(id_mazo, mazo)
    etiqueta = "".join(c if c.isalnum() else "_" for c in mazo)[:40]
    for t in tarjetas:
        baraja.add_note(genanki.Note(model=modelo, tags=[etiqueta], fields=[
            t["pregunta"], t["respuesta"], str(t.get("pagina") or "")]))
    salida.parent.mkdir(parents=True, exist_ok=True)
    genanki.Package(baraja).write_to_file(str(salida))
    return salida


# --- examen -----------------------------------------------------------------------------

EJEMPLO_EXAMEN = {"preguntas": [
    {"tipo": "test", "pregunta": "…", "opciones": ["a", "b", "c", "d"], "correcta": 0,
     "pagina": 1},
    {"tipo": "corta", "pregunta": "…", "respuesta": "…", "pagina": 2},
]}


def _normalizar_preguntas(respuesta: Any, tipo: str) -> list[dict]:
    if isinstance(respuesta, dict):
        respuesta = respuesta.get("preguntas") or []
    salida = []
    for p in respuesta if isinstance(respuesta, list) else []:
        if not isinstance(p, dict) or not p.get("pregunta"):
            continue
        opciones = p.get("opciones")
        if isinstance(opciones, list) and len(opciones) >= 2 and tipo != "corta":
            try:
                correcta = int(p.get("correcta", 0))
            except (TypeError, ValueError):
                correcta = 0
            salida.append({"tipo": "test", "pregunta": p["pregunta"],
                           "opciones": [str(o) for o in opciones][:4],
                           "correcta": max(0, min(correcta, len(opciones) - 1)),
                           "pagina": p.get("pagina")})
        elif p.get("respuesta") and tipo != "test":
            salida.append({"tipo": "corta", "pregunta": p["pregunta"],
                           "respuesta": str(p["respuesta"]), "pagina": p.get("pagina")})
    return salida


def generar_examen(archivo: Path, n: int = 10, tipo: str = "mixto") -> list[dict]:
    h, paginas = cargar(archivo)
    instruccion = {
        "test": "preguntas tipo test con 4 opciones y el índice (0-3) de la correcta",
        "corta": "preguntas de respuesta corta con su respuesta modelo",
        "mixto": "preguntas mezclando tipo test (4 opciones) y respuesta corta",
    }.get(tipo, "preguntas")

    def calcular() -> list[dict]:
        texto = extraer.texto_con_paginas(paginas)
        trozos = util.trocear(texto, max_chars=5000)
        por_trozo = max(1, -(-n // len(trozos)))
        todas: list[dict] = []
        for trozo in trozos:
            todas += _normalizar_preguntas(util.pedir_json(
                f"Crea {por_trozo} {instruccion} sobre este texto. Indica la página.\n\n{trozo}",
                EJEMPLO_EXAMEN), tipo)
            if len(todas) >= n:
                break
        return todas[:n]

    return _cacheado(_clave("examen", h, n, tipo), calcular)


def corregir_corta(pregunta: str, modelo: str, respuesta: str) -> dict:
    r = util.pedir_json(
        "Corrige la respuesta de un estudiante. Pon una nota de 0 a 10 y un comentario breve.\n"
        f"PREGUNTA: {pregunta}\nRESPUESTA MODELO: {modelo}\nRESPUESTA DEL ESTUDIANTE: {respuesta}",
        {"nota": 7, "comentario": "…"})
    try:
        nota = float(r.get("nota", 0)) if isinstance(r, dict) else 0.0
    except (TypeError, ValueError):
        nota = 0.0
    comentario = r.get("comentario", "") if isinstance(r, dict) else ""
    return {"nota": max(0.0, min(10.0, nota)), "comentario": str(comentario)}


# --- pregunta sobre el documento -----------------------------------------------------------


def contexto_pregunta(archivo: Path, duda: str, n: int = 4) -> tuple[str, list[int]]:
    _, paginas = cargar(archivo)
    elegidos = bm25.mejores(paginas, duda, n)
    if not elegidos:
        elegidos = bm25.trozos(paginas)[:n]
    texto = "\n\n".join(f"[p. {p}] {t}" for p, t in elegidos)
    prompt = (f"Responde a la duda usando SOLO estos fragmentos del documento y cita las páginas "
              f"así: [p. 12]. Si no está en el texto, dilo.\n\nFRAGMENTOS:\n{texto}\n\n"
              f"DUDA: {duda}")
    return prompt, sorted({p for p, _ in elegidos})


# --- esquema ---------------------------------------------------------------------------------

EJEMPLO_ARBOL = {"concepto": "Tema", "hijos": [{"concepto": "Idea", "hijos": [
    {"concepto": "Detalle", "hijos": []}]}]}


def podar(nodo: Any, nivel: int = 0, maximo: int = 3) -> dict:
    if not isinstance(nodo, dict):
        return {"concepto": str(nodo), "hijos": []}
    hijos = (nodo.get("hijos") or []) if nivel < maximo - 1 else []
    return {"concepto": str(nodo.get("concepto") or nodo.get("titulo") or "?")[:80],
            "hijos": [podar(h, nivel + 1, maximo) for h in hijos][:8]}


def generar_esquema(archivo: Path) -> dict:
    h, paginas = cargar(archivo)

    def calcular() -> dict:
        texto = extraer.texto_plano(paginas)
        if len(texto) > 6000:
            texto = util.resumir_largo(texto, NIVELES_RESUMEN["esquema"])
        return podar(util.pedir_json(
            "Convierte este contenido en un mapa conceptual: un árbol de conceptos de 3 niveles "
            f"como máximo, con nombres cortos.\n\n{texto}", EJEMPLO_ARBOL))

    return _cacheado(_clave("esquema", h), calcular)


def a_mermaid(arbol: dict) -> str:
    lineas = ["mindmap", f"  root(({arbol['concepto']}))"]

    def recorrer(nodo: dict, nivel: int) -> None:
        for h in nodo["hijos"]:
            lineas.append("  " * (nivel + 1) + h["concepto"].replace("(", "").replace(")", ""))
            recorrer(h, nivel + 1)

    recorrer(arbol, 1)
    return "\n".join(lineas)


def a_png(arbol: dict, salida: Path, paleta: dict[str, str]) -> Path:
    """Dibuja el árbol de izquierda a derecha con cajas y líneas."""
    from PIL import Image, ImageDraw, ImageFont

    try:
        fuente = ImageFont.truetype("DejaVuSans.ttf", 18)
    except OSError:
        fuente = ImageFont.load_default()
    ancho_col, alto_fila, margen = 300, 54, 40
    posiciones: list[tuple[dict, int, float]] = []

    def colocar(nodo: dict, nivel: int, fila: list[int]) -> float:
        if not nodo["hijos"]:
            y = fila[0]
            fila[0] += 1
        else:
            ys = [colocar(h, nivel + 1, fila) for h in nodo["hijos"]]
            y = sum(ys) / len(ys)
        posiciones.append((nodo, nivel, y))
        return y

    filas = [0]
    colocar(arbol, 0, filas)
    niveles = max(n for _, n, _ in posiciones) + 1
    img = Image.new("RGB", (margen * 2 + niveles * ancho_col, margen * 2 + filas[0] * alto_fila),
                    paleta.get("fondo", "#1E1F22"))
    d = ImageDraw.Draw(img)
    centro = {id(n): (margen + nivel * ancho_col, margen + y * alto_fila)
              for n, nivel, y in posiciones}
    for nodo, _, _ in posiciones:
        x, y = centro[id(nodo)]
        for h in nodo["hijos"]:
            hx, hy = centro[id(h)]
            d.line([(x + 240, y + 18), (hx, hy + 18)], fill=paleta.get("apagado", "#6B6B6B"),
                   width=2)
    for nodo, nivel, _ in posiciones:
        x, y = centro[id(nodo)]
        color = paleta.get("acento" if nivel == 0 else "primario", "#8FBC8F")
        d.rounded_rectangle([x, y, x + 240, y + 36], radius=8, outline=color, width=2)
        d.text((x + 10, y + 8), nodo["concepto"][:26], fill=paleta.get("texto", "#C8C8C8"),
               font=fuente)
    salida.parent.mkdir(parents=True, exist_ok=True)
    img.save(salida)
    return salida


# --- explica -----------------------------------------------------------------------------------

NIVELES_EXPLICA = {
    "1": "como a un niño de 12 años, con un ejemplo cotidiano",
    "2": "a nivel de estudiante, con un ejemplo",
    "3": "a nivel experto, con precisión técnica y un ejemplo avanzado",
}


def prompt_explica(concepto: str, nivel: str = "todos") -> str:
    if nivel in NIVELES_EXPLICA:
        como = NIVELES_EXPLICA[nivel]
        return (f"Explica «{concepto}» {como}. Termina con una pregunta corta para comprobar "
                "que se ha entendido.")
    return (f"Explica «{concepto}» en tres niveles, con un título para cada uno: "
            "### Simple (para un niño de 12 años), ### Normal y ### Experto. "
            "Pon un ejemplo en cada nivel y termina con una pregunta de comprobación.")


def explicar(concepto: str, nivel: str = "todos") -> str:
    return preguntar(prompt_explica(concepto, nivel))
