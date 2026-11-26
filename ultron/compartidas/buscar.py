"""`ultron buscar`: busca por contenido (txt, md, pdf, docx, código) con un índice en caché."""

from __future__ import annotations

import hashlib
from pathlib import Path

import typer
from rich.text import Text

from ultron.modos.focus.bm25 import BM25, normalizar, tokens
from ultron.nucleo import jsonio, rutas
from ultron.ui import tema

app = typer.Typer()
TEXTO = {".txt", ".md", ".csv", ".py", ".js", ".ts", ".java", ".c", ".cpp", ".h", ".rs", ".go",
         ".sh", ".html", ".css", ".json", ".yaml", ".yml", ".toml", ".sql", ".lua", ".tex"}
DOCUMENTOS = {".pdf", ".docx"}
MAX_CHARS = 20000
MAX_ARCHIVOS = 5000


def _leer(ruta: Path) -> str:
    sufijo = ruta.suffix.lower()
    try:
        if sufijo in TEXTO:
            return ruta.read_text(encoding="utf-8", errors="ignore")[:MAX_CHARS]
        if sufijo in DOCUMENTOS:
            from ultron.modos.focus.extraer import extraer, texto_plano

            return texto_plano(extraer(ruta))[:MAX_CHARS]
    except Exception:  # noqa: BLE001 - un archivo roto no para la búsqueda
        return ""
    return ""


def ruta_indice(carpeta: Path) -> Path:
    h = hashlib.sha1(str(carpeta.resolve()).encode()).hexdigest()[:16]
    return rutas.cache() / "buscar" / f"{h}.json"


def indexar(carpeta: Path) -> dict[str, dict]:
    """Índice incremental: solo relee los archivos cuya fecha de modificación ha cambiado."""
    previo = jsonio.leer(ruta_indice(carpeta), {}) or {}
    nuevo: dict[str, dict] = {}
    for n, ruta in enumerate(sorted(carpeta.rglob("*"))):
        if n > MAX_ARCHIVOS * 4:
            break
        rel = ruta.relative_to(carpeta)
        if any(p.startswith(".") or p in ("node_modules", "__pycache__") for p in rel.parts):
            continue
        if not ruta.is_file() or ruta.suffix.lower() not in TEXTO | DOCUMENTOS:
            continue
        clave = str(rel)
        mtime = ruta.stat().st_mtime
        if clave in previo and previo[clave].get("mtime") == mtime:
            nuevo[clave] = previo[clave]
        else:
            nuevo[clave] = {"mtime": mtime, "texto": _leer(ruta)}
        if len(nuevo) >= MAX_ARCHIVOS:
            break
    jsonio.escribir(ruta_indice(carpeta), nuevo)
    return nuevo


def fragmento(texto: str, consulta: str, ancho: int = 110) -> str:
    plano = " ".join(texto.split())
    normal = normalizar(plano)
    pos = -1
    for palabra in consulta.split():
        pos = normal.find(normalizar(palabra))
        if pos >= 0:
            break
    inicio = max(0, pos - ancho // 3) if pos >= 0 else 0
    return ("…" if inicio else "") + plano[inicio : inicio + ancho] + "…"


def buscar(carpeta: Path, consulta: str, n: int = 10) -> list[tuple[str, float, str]]:
    indice = indexar(carpeta)
    nombres = list(indice)
    if not nombres:
        return []
    docs = [f"{nombre} {nombre} {indice[nombre]['texto']}" for nombre in nombres]
    resultados = BM25(docs).puntuar(consulta)[:n]
    return [(nombres[i], p, fragmento(indice[nombres[i]]["texto"], consulta))
            for i, p in resultados]


@app.command("buscar")
def cmd_buscar(
    consulta: str = typer.Argument(..., help="Qué buscas (palabras clave o una frase)."),
    carpeta: Path = typer.Argument(None, file_okay=False, help="Dónde (por defecto, tu carpeta)."),
    ia: bool = typer.Option(False, "--ia", help="La IA mejora la consulta y resume."),
    n: int = typer.Option(10, "--n", help="Número de resultados."),
) -> None:
    """Busca archivos por lo que contienen, no solo por el nombre."""
    t = tema.actual()
    carpeta = (carpeta or rutas.home()).resolve()
    consulta_final = consulta
    if ia:
        from ultron.ia.cliente import preguntar

        consulta_final = preguntar(
            "Reescribe esta búsqueda como 5-8 palabras clave (sinónimos incluidos), en una sola "
            f"línea y sin explicaciones: {consulta}").strip().splitlines()[0]
        t.info(f"buscando: {consulta_final}")
    if not tokens(consulta_final):
        t.error("La búsqueda está vacía.")
        raise typer.Exit(1)
    with t.spinner_ctx(f"indexando {carpeta}"):
        resultados = buscar(carpeta, consulta_final, n)
    if not resultados:
        t.info("Sin resultados.")
        return
    for nombre, puntos, texto in resultados:
        t.consola.print(Text(nombre, style="bold acento"), Text(f"  {puntos:.1f}", style="apagado"))
        t.consola.print(Text(f"   {texto}", style="texto"))
    if ia:
        from ultron.ia.cliente import preguntar

        lista = "\n".join(f"- {n}: {f}" for n, _, f in resultados)
        t.consola.print(t.panel(preguntar(
            f"El usuario buscaba «{consulta}». Di en 2 frases qué archivos parecen más útiles y "
            f"por qué:\n{lista}"), titulo="resumen"))
