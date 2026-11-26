"""`ultron ordenar <carpeta>`: ordena archivos por reglas o con IA, con vista previa y deshacer."""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path, PurePosixPath

import typer
import yaml
from rich.text import Text
from rich.tree import Tree

from ultron.nucleo import jsonio, rutas
from ultron.ui import tema

app = typer.Typer()

CATEGORIAS: dict[str, tuple[str, ...]] = {
    "Documentos": (".pdf", ".doc", ".docx", ".odt", ".txt", ".md", ".rtf", ".xls", ".xlsx",
                   ".ods", ".csv", ".ppt", ".pptx", ".odp", ".epub"),
    "Imágenes": (".jpg", ".jpeg", ".png", ".gif", ".webp", ".svg", ".heic", ".bmp", ".tif",
                 ".tiff", ".raw", ".xcf", ".psd", ".kra"),
    "Vídeos": (".mp4", ".mkv", ".mov", ".avi", ".webm", ".m4v", ".flv"),
    "Música": (".mp3", ".flac", ".ogg", ".oga", ".wav", ".m4a", ".aac", ".opus"),
    "Comprimidos": (".zip", ".tar", ".gz", ".tgz", ".xz", ".bz2", ".7z", ".rar", ".zst"),
    "Código": (".py", ".js", ".ts", ".java", ".c", ".cpp", ".h", ".rs", ".go", ".sh", ".html",
               ".css", ".json", ".yaml", ".yml", ".toml", ".ipynb", ".sql", ".lua"),
    "Instaladores": (".deb", ".rpm", ".appimage", ".flatpakref", ".exe", ".msi", ".run", ".snap"),
}
LOTE = 40
MAX_NIVELES = 3


@dataclass
class Archivo:
    ruta: Path
    rel: str
    tamano: int
    fecha: datetime
    extracto: str = ""


# --- inventario --------------------------------------------------------------------


def _extracto(ruta: Path) -> str:
    sufijo = ruta.suffix.lower()
    try:
        if sufijo in (".txt", ".md", ".csv"):
            return ruta.read_text(encoding="utf-8", errors="ignore")[:500]
        if sufijo in (".pdf", ".docx"):
            from ultron.modos.focus.extraer import extraer, texto_plano

            return texto_plano(extraer(ruta)[:2])[:500]
    except Exception:  # noqa: BLE001 - un archivo raro no debe parar el inventario
        return ""
    return ""


def inventario(carpeta: Path, recursivo: bool = False, con_extracto: bool = True) -> list[Archivo]:
    archivos = []
    patron = carpeta.rglob("*") if recursivo else carpeta.iterdir()
    for ruta in sorted(patron):
        rel = ruta.relative_to(carpeta)
        if any(p.startswith(".") for p in rel.parts) or not ruta.is_file():
            continue
        st = ruta.stat()
        archivos.append(Archivo(
            ruta, rel.as_posix(), st.st_size, datetime.fromtimestamp(st.st_mtime),
            _extracto(ruta) if con_extracto else ""))
    return archivos


def carpetas_existentes(carpeta: Path) -> list[str]:
    salida = []
    for d in sorted(carpeta.rglob("*")):
        rel = d.relative_to(carpeta)
        if d.is_dir() and not any(p.startswith(".") for p in rel.parts) and len(rel.parts) <= 3:
            salida.append(rel.as_posix())
    return salida


# --- planes ----------------------------------------------------------------------------


def categoria(nombre: str) -> str:
    sufijo = Path(nombre).suffix.lower()
    for cat, sufijos in CATEGORIAS.items():
        if sufijo in sufijos:
            return cat
    return "Otros"


def plan_reglas(archivos: list[Archivo], por_fecha: bool = False) -> dict[str, str]:
    plan = {}
    for a in archivos:
        destino = categoria(a.rel)
        if por_fecha:
            destino = f"{destino}/{a.fecha:%Y}/{a.fecha:%m}"
        plan[a.rel] = destino
    return plan


def validar_destino(destino: object) -> str | None:
    """Carpeta relativa segura y de 3 niveles como mucho, o None si no vale."""
    if not isinstance(destino, str):
        return None
    texto = destino.strip().replace("\\", "/").strip("/")
    if not texto or texto.startswith("~") or re.match(r"^[a-zA-Z]:", texto):
        return None
    if destino.strip().startswith(("/", "\\")):
        return None
    partes = [p.strip() for p in PurePosixPath(texto).parts]
    if any(p in ("..", ".", "") or p.startswith(".") for p in partes):
        return None
    partes = [re.sub(r'[<>:"|?*\x00-\x1f]', "", p)[:60] for p in partes]
    if not all(partes) or len(partes) > MAX_NIVELES:
        return None
    return "/".join(partes)


def plan_ia(archivos: list[Archivo], carpeta: Path) -> dict[str, str]:
    from ultron.ia.util import pedir_json

    existentes = carpetas_existentes(carpeta)
    plan: dict[str, str] = {}
    for i in range(0, len(archivos), LOTE):
        lote = archivos[i : i + LOTE]
        lista = "\n".join(
            f"- {a.rel}" + (f" :: {a.extracto[:160]!r}" if a.extracto else "") for a in lote)
        respuesta = pedir_json(
            "Organiza estos archivos en carpetas con sentido (por asignatura, proyecto o tema). "
            "Reutiliza las carpetas existentes si encajan y crea las que falten, con 3 niveles "
            "como máximo y nombres cortos en español. Responde con la carpeta de destino de cada "
            f"archivo (ruta relativa).\n\nCARPETAS EXISTENTES:\n"
            f"{chr(10).join(existentes) or '(ninguna)'}\n\nARCHIVOS:\n{lista}",
            {"asignaciones": {"apuntes-tema1.pdf": "Universidad/Matemáticas/Apuntes"}},
        )
        asignaciones = respuesta.get("asignaciones", respuesta) if isinstance(respuesta, dict) \
            else {}
        nombres = {a.rel for a in lote}
        for archivo, destino in (asignaciones or {}).items():
            valido = validar_destino(destino)
            if archivo in nombres and valido:
                plan[archivo] = valido
        for a in lote:
            plan.setdefault(a.rel, categoria(a.rel))
    return plan


# --- aplicar / deshacer -----------------------------------------------------------------


def _libre(destino: Path) -> Path:
    if not destino.exists():
        return destino
    n = 2
    while True:
        candidato = destino.with_name(f"{destino.stem} ({n}){destino.suffix}")
        if not candidato.exists():
            return candidato
        n += 1


def dir_diarios() -> Path:
    return rutas.estado() / "ordenar"


def aplicar(carpeta: Path, plan: dict[str, str]) -> dict:
    ident = datetime.now().strftime("%Y%m%d-%H%M%S")
    diario = {"id": ident, "carpeta": str(carpeta), "movimientos": [], "creadas": []}
    for rel, destino_dir in plan.items():
        origen = carpeta / rel
        if not origen.exists() or PurePosixPath(rel).parent.as_posix() == destino_dir:
            continue
        objetivo_dir = carpeta / destino_dir
        for k in range(len(PurePosixPath(destino_dir).parts)):
            sub = carpeta / "/".join(PurePosixPath(destino_dir).parts[: k + 1])
            if not sub.exists():
                diario["creadas"].append(str(sub))
        objetivo_dir.mkdir(parents=True, exist_ok=True)
        objetivo = _libre(objetivo_dir / origen.name)
        shutil.move(str(origen), str(objetivo))
        diario["movimientos"].append({"de": str(origen), "a": str(objetivo)})
    if diario["movimientos"]:
        jsonio.escribir(dir_diarios() / f"{ident}.json", diario)
    return diario


def ultimo_diario() -> Path | None:
    diarios = sorted(dir_diarios().glob("*.json")) if dir_diarios().exists() else []
    return diarios[-1] if diarios else None


def deshacer(ident: str | None = None) -> int:
    ruta = dir_diarios() / f"{ident}.json" if ident else ultimo_diario()
    if ruta is None or not ruta.exists():
        raise FileNotFoundError("No hay nada que deshacer.")
    diario = jsonio.leer(ruta, {})
    n = 0
    for mov in reversed(diario.get("movimientos", [])):
        actual, original = Path(mov["a"]), Path(mov["de"])
        if actual.exists():
            original.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(actual), str(_libre(original)))
            n += 1
    for creada in sorted(diario.get("creadas", []), key=len, reverse=True):
        d = Path(creada)
        if d.is_dir() and not any(d.iterdir()):
            d.rmdir()
    ruta.unlink()
    return n


# --- vista previa -------------------------------------------------------------------------


def arbol_previo(carpeta: Path, plan: dict[str, str]) -> Tree:
    existentes = set(carpetas_existentes(carpeta))
    raiz = Tree(Text(f"{carpeta.name}/", style="bold primario"), guide_style="apagado")
    nodos: dict[str, Tree] = {}
    por_dir: dict[str, list[str]] = {}
    for rel, destino in sorted(plan.items(), key=lambda x: (x[1], x[0])):
        por_dir.setdefault(destino, []).append(rel)
    for destino in sorted(por_dir):
        padre = raiz
        acumulado = []
        for parte in PurePosixPath(destino).parts:
            acumulado.append(parte)
            clave = "/".join(acumulado)
            if clave not in nodos:
                nueva = clave not in existentes
                etiqueta = Text(f"{parte}/", style="bold ok" if nueva else "bold texto")
                if nueva:
                    etiqueta.append("  nueva", style="apagado")
                nodos[clave] = padre.add(etiqueta)
            padre = nodos[clave]
        for rel in por_dir[destino]:
            queda = PurePosixPath(rel).parent.as_posix() == destino
            padre.add(Text(PurePosixPath(rel).name, style="apagado" if queda else "acento"))
    return raiz


def _editar(plan: dict[str, str]) -> dict[str, str]:
    with tempfile.NamedTemporaryFile("w", suffix=".yaml", delete=False, encoding="utf-8") as f:
        f.write("# archivo: carpeta de destino (relativa). Guarda y cierra para seguir.\n")
        yaml.safe_dump(plan, f, allow_unicode=True, sort_keys=True)
        ruta = f.name
    editor = os.environ.get("EDITOR") or ("notepad" if os.name == "nt" else "nano")
    subprocess.call([editor, ruta])
    nuevo = yaml.safe_load(Path(ruta).read_text(encoding="utf-8")) or {}
    Path(ruta).unlink(missing_ok=True)
    return {k: v for k, v in ((k, validar_destino(v)) for k, v in nuevo.items()) if v}


@app.command("ordenar")
def cmd_ordenar(
    carpeta: Path = typer.Argument(None, file_okay=False, help="Carpeta a ordenar."),
    sin_ia: bool = typer.Option(False, "--sin-ia", help="Solo por tipo de archivo."),
    por_fecha: bool = typer.Option(False, "--por-fecha", help="Por tipo, año y mes."),
    recursivo: bool = typer.Option(False, "--recursivo", "-r", help="Incluye subcarpetas."),
    simular: bool = typer.Option(False, "--simular", help="Solo enseña el plan."),
    si: bool = typer.Option(False, "--si", "-y", help="No preguntes."),
    deshacer_: bool = typer.Option(False, "--deshacer", help="Deshace la última ordenación."),
    id_diario: str = typer.Option(None, "--id", help="Con --deshacer: qué ordenación."),
) -> None:
    """Ordena una carpeta: la IA decide dónde va cada archivo (creando carpetas si hace falta)."""
    t = tema.actual()
    if deshacer_:
        try:
            n = deshacer(id_diario)
        except FileNotFoundError as e:
            t.error(str(e))
            raise typer.Exit(1) from None
        t.ok(f"{n} archivos devueltos a su sitio.")
        return
    if carpeta is None or not carpeta.is_dir():
        t.error("Indica una carpeta que exista: ultron ordenar ~/Descargas")
        raise typer.Exit(1)
    carpeta = carpeta.resolve()
    with t.spinner_ctx("haciendo inventario"):
        archivos = inventario(carpeta, recursivo, con_extracto=not sin_ia)
    if not archivos:
        t.info("No hay archivos que ordenar.")
        return
    if sin_ia or por_fecha:
        plan = plan_reglas(archivos, por_fecha)
    else:
        from ultron.ia.cliente import hay_ia

        if not hay_ia():
            t.aviso("No hay IA configurada: ordeno por tipo de archivo (--sin-ia).")
            plan = plan_reglas(archivos)
        else:
            with t.spinner_ctx(f"la IA está pensando dónde va cada uno ({len(archivos)})"):
                plan = plan_ia(archivos, carpeta)
    while True:
        movidos = sum(PurePosixPath(r).parent.as_posix() != d for r, d in plan.items())
        t.consola.print(t.panel(arbol_previo(carpeta, plan), titulo="plan de ordenación"))
        t.info(f"{movidos} archivos se moverán · {len(plan) - movidos} se quedan.")
        if simular:
            return
        if si:
            break
        opcion = typer.prompt("¿Aplicar? (s/n/editar)", default="s").strip().lower()
        if opcion.startswith("e"):
            plan = _editar(plan) or plan
            continue
        if not opcion.startswith("s"):
            t.info("No se ha movido nada.")
            return
        break
    diario = aplicar(carpeta, plan)
    t.ok(f"{len(diario['movimientos'])} archivos ordenados. "
         f"Deshacer: ultron ordenar --deshacer --id {diario['id']}")
