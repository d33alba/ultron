"""Generador de temas de iconos: recolorea Yaru (PNG y SVG), añade emblemas e iconos propios.

Uso desde la terminal: python -m ultron.capas.iconos_gen <modo>
"""

from __future__ import annotations

import base64
import colorsys
import os
import re
import shutil
from collections.abc import Callable
from concurrent.futures import ProcessPoolExecutor
from dataclasses import asdict, dataclass, field
from pathlib import Path

from ultron.capas import comun as C

VERSION = 4
CATEGORIAS = ("apps", "places", "mimetypes", "devices", "status", "actions", "categories",
              "emblems", "legacy")
BASES = [Path("/usr/share/icons/Yaru"), Path("/usr/share/icons/Adwaita")]
_HEX = re.compile(r"#([0-9a-fA-F]{6}|[0-9a-fA-F]{3})\b")
_RGB = re.compile(r"rgb\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*\)")


@dataclass
class Ajustes:
    objetivo: str = "#0038B8"
    intensidad: float = 0.85
    saturacion: float = 1.0
    umbral: float = 0.18          # saturación mínima para considerar un píxel "de color"
    monocromo: bool = False
    opacidad: float = 1.0
    glow: float = 0.0
    por_categoria: dict[str, str] = field(default_factory=dict)   # categoría -> color
    emblema: str | None = None    # ruta absoluta a PNG
    emblema_en: list[str] = field(default_factory=lambda: ["places"])

    def color_de(self, categoria: str) -> str:
        return self.por_categoria.get(categoria, self.objetivo)


# --- transformación de colores -----------------------------------------------------
def transformar_rgb(rgb: tuple[int, int, int], aj: Ajustes, objetivo: str) -> tuple[int, int, int]:
    r, g, b = (c / 255 for c in rgb)
    h, s, v = colorsys.rgb_to_hsv(r, g, b)
    if aj.monocromo:
        gris = 0.3 * r + 0.59 * g + 0.11 * b
        th, ts, _ = colorsys.rgb_to_hsv(*(c / 255 for c in C.hex_a_rgb(objetivo)))
        nr, ng, nb = colorsys.hsv_to_rgb(th, min(ts, 0.18), gris)
    elif s < aj.umbral:
        return rgb
    else:
        th, ts, tv = colorsys.rgb_to_hsv(*(c / 255 for c in C.hex_a_rgb(objetivo)))
        ns = min(1.0, max(s, ts) * aj.saturacion)
        nv = v * 0.55 + tv * 0.45
        nr, ng, nb = colorsys.hsv_to_rgb(th, ns, nv)
    mezcla = 1.0 if aj.monocromo else aj.intensidad
    return tuple(round((o / 255 * (1 - mezcla) + n * mezcla) * 255)
                 for o, n in zip(rgb, (nr, ng, nb), strict=True))


def recolorear_imagen(img, aj: Ajustes, objetivo: str):
    """Recolorea una imagen RGBA de Pillow."""
    from PIL import Image, ImageFilter

    img = img.convert("RGBA")
    alfa = img.getchannel("A")
    hsv = img.convert("RGB").convert("HSV")
    h, s, v = hsv.split()
    th, ts, tv = colorsys.rgb_to_hsv(*(c / 255 for c in C.hex_a_rgb(objetivo)))
    if aj.monocromo:
        gris = img.convert("L")
        tinte = Image.merge("HSV", (
            Image.new("L", img.size, round(th * 255)),
            Image.new("L", img.size, round(min(ts, 0.18) * 255)),
            gris,
        )).convert("RGB")
        nuevo = tinte
    else:
        mascara = s.point(lambda x: 255 if x > aj.umbral * 255 else 0)
        h2 = Image.composite(Image.new("L", img.size, round(th * 255)), h, mascara)
        s2 = Image.composite(
            s.point(lambda x: min(255, round(max(x, ts * 255) * aj.saturacion))), s, mascara)
        v2 = Image.composite(v.point(lambda x: round(x * 0.55 + tv * 255 * 0.45)), v, mascara)
        nuevo = Image.merge("HSV", (h2, s2, v2)).convert("RGB")
        nuevo = Image.blend(img.convert("RGB"), nuevo, aj.intensidad)
    if aj.opacidad < 1:
        alfa = alfa.point(lambda x: round(x * aj.opacidad))
    nuevo.putalpha(alfa)
    if aj.glow > 0:
        halo = Image.new("RGBA", nuevo.size, objetivo)
        halo.putalpha(alfa.filter(ImageFilter.GaussianBlur(aj.glow)).point(lambda a: a // 2))
        return Image.alpha_composite(halo, nuevo)
    return nuevo


def recolorear_svg(texto: str, aj: Ajustes, objetivo: str) -> str:
    def hexa(m: re.Match) -> str:
        valor = m.group(1)
        if len(valor) == 3:
            valor = "".join(c * 2 for c in valor)
        return C.rgb_a_hex(transformar_rgb(C.hex_a_rgb(valor), aj, objetivo))

    def rgb(m: re.Match) -> str:
        r, g, b = (int(x) for x in m.groups())
        nr, ng, nb = transformar_rgb((r, g, b), aj, objetivo)
        return f"rgb({nr},{ng},{nb})"

    texto = _HEX.sub(hexa, texto)
    texto = _RGB.sub(rgb, texto)
    if aj.opacidad < 1 and "<svg" in texto:
        texto = re.sub(r"<svg\b", f'<svg opacity="{aj.opacidad:.2f}"', texto, count=1)
    return texto


# --- emblemas ----------------------------------------------------------------------
def poner_emblema_png(img, emblema_png: Path):
    from PIL import Image

    marca = Image.open(emblema_png).convert("RGBA")
    lado = max(6, round(min(img.size) * 0.42))
    marca = marca.resize((lado, lado), Image.LANCZOS)
    img = img.copy()
    img.alpha_composite(marca, (img.size[0] - lado, img.size[1] - lado))
    return img


def poner_emblema_svg(texto: str, emblema_png: Path) -> str:
    m = re.search(r'viewBox="([\d.\s-]+)"', texto)
    if m:
        x0, y0, ancho, alto = (float(v) for v in m.group(1).split())
    else:
        w = re.search(r'width="([\d.]+)', texto)
        h = re.search(r'height="([\d.]+)', texto)
        x0, y0 = 0.0, 0.0
        ancho = float(w.group(1)) if w else 16.0
        alto = float(h.group(1)) if h else 16.0
    lado = min(ancho, alto) * 0.42
    datos = base64.b64encode(emblema_png.read_bytes()).decode("ascii")
    imagen = (f'<image x="{x0 + ancho - lado:.2f}" y="{y0 + alto - lado:.2f}" '
              f'width="{lado:.2f}" height="{lado:.2f}" '
              f'href="data:image/png;base64,{datos}"/>')
    return texto.replace("</svg>", imagen + "</svg>", 1) if "</svg>" in texto else texto


# --- un archivo ------------------------------------------------------------------------
def _categoria(rel: Path) -> str | None:
    for parte in rel.parts:
        if parte in CATEGORIAS:
            return parte
    return None


def _lleva_emblema(rel: Path, aj: Ajustes) -> bool:
    cat = _categoria(rel)
    return bool(aj.emblema) and cat in aj.emblema_en and (
        cat != "places" or rel.stem.startswith(("folder", "user-", "inode-directory"))
    )


def procesar(origen: str, destino: str, rel: str, aj_dict: dict) -> None:
    """Procesa un icono (función de nivel superior para poder usarla en procesos)."""
    aj = Ajustes(**aj_dict)
    origen_p, destino_p, rel_p = Path(origen), Path(destino), Path(rel)
    destino_p.parent.mkdir(parents=True, exist_ok=True)
    objetivo = aj.color_de(_categoria(rel_p) or "")
    emblema = Path(aj.emblema) if aj.emblema and Path(aj.emblema).exists() else None
    if origen_p.suffix == ".svg":
        texto = recolorear_svg(origen_p.read_text(encoding="utf-8", errors="ignore"), aj, objetivo)
        if emblema and _lleva_emblema(rel_p, aj):
            texto = poner_emblema_svg(texto, emblema)
        destino_p.write_text(texto, encoding="utf-8")
        return
    from PIL import Image

    with Image.open(origen_p) as img:
        nuevo = recolorear_imagen(img, aj, objetivo)
    if emblema and _lleva_emblema(rel_p, aj):
        nuevo = poner_emblema_png(nuevo, emblema)
    nuevo.save(destino_p)


# --- tema completo ------------------------------------------------------------------------
def base_disponible(bases: list[Path] | None = None) -> Path | None:
    for b in bases or BASES:
        if (b / "index.theme").exists():
            return b
    return None


def _index_theme(base: Path, nombre: str) -> str:
    texto = (base / "index.theme").read_text(encoding="utf-8", errors="ignore")
    texto = re.sub(r"(?m)^Name=.*$", f"Name={nombre}", texto, count=1)
    herencia = f"Inherits={base.name},Adwaita,hicolor"
    if re.search(r"(?m)^Inherits=", texto):
        texto = re.sub(r"(?m)^Inherits=.*$", herencia, texto, count=1)
    else:
        texto = texto.replace("[Icon Theme]", f"[Icon Theme]\n{herencia}", 1)
    return texto


def _personalizados(dir_iconos: Path | None) -> list[Path]:
    if not dir_iconos or not dir_iconos.is_dir():
        return []
    return sorted(p for p in dir_iconos.iterdir() if p.suffix.lower() in (".png", ".svg"))


def _copiar_personalizados(destino: Path, propios: list[Path]) -> int:
    """Pone cada icono propio en todos los tamaños de apps/ (y scalable/)."""
    from PIL import Image

    carpetas = sorted({p.parent for p in destino.rglob("*") if p.parent.name == "apps"})
    if not carpetas:
        carpetas = [destino / "scalable" / "apps"]
    n = 0
    for icono in propios:
        for carpeta in carpetas:
            tamano = re.match(r"(\d+)x\d+", carpeta.parent.name) or re.match(
                r"(\d+)x\d+", carpeta.parent.parent.name if carpeta.parent.parent else "")
            carpeta.mkdir(parents=True, exist_ok=True)
            if icono.suffix.lower() == ".svg":
                if "scalable" in carpeta.parts or not tamano:
                    shutil.copy2(icono, carpeta / icono.name)
                    n += 1
                continue
            lado = int(tamano.group(1)) if tamano else 256
            with Image.open(icono) as img:
                img.convert("RGBA").resize((lado, lado), Image.LANCZOS).save(
                    carpeta / f"{icono.stem}.png")
            n += 1
    return n


def generar(
    id_modo: str,
    aj: Ajustes,
    destino: Path,
    *,
    base: Path | None = None,
    dir_personalizados: Path | None = None,
    progreso: Callable[[int, int], None] | None = None,
    procesos: int | None = None,
) -> dict:
    """Genera el tema en `destino`. Devuelve {"generado": bool, "iconos": n, "huella": h}."""
    base = base or base_disponible()
    if base is None:
        raise FileNotFoundError("No encuentro un tema de iconos base (Yaru o Adwaita).")
    propios = _personalizados(dir_personalizados)
    firma = C.huella(VERSION, str(base), asdict(aj),
                     [(p.name, p.stat().st_mtime_ns) for p in propios])
    marca = destino / ".ultron-huella"
    if marca.exists() and marca.read_text(encoding="utf-8").strip() == firma:
        return {"generado": False, "iconos": 0, "huella": firma}

    if destino.exists():
        shutil.rmtree(destino)
    destino.mkdir(parents=True)
    trabajos: list[tuple[str, str, str]] = []
    enlaces: list[tuple[Path, str]] = []
    for ruta in base.rglob("*"):
        rel = ruta.relative_to(base)
        if ruta.is_dir() or _categoria(rel) is None:
            continue
        if ruta.suffix.lower() not in (".png", ".svg"):
            continue
        if ruta.is_symlink():
            enlaces.append((destino / rel, os.readlink(ruta)))
            continue
        trabajos.append((str(ruta), str(destino / rel), str(rel)))

    aj_dict = asdict(aj)
    total = len(trabajos)
    hechos = 0
    if total > 300 and (procesos is None or procesos > 1):
        with ProcessPoolExecutor(max_workers=procesos) as pool:
            for _ in pool.map(procesar, *zip(*trabajos, strict=True), [aj_dict] * total,
                              chunksize=64):
                hechos += 1
                if progreso and hechos % 100 == 0:
                    progreso(hechos, total)
    else:
        for origen, dest, rel in trabajos:
            procesar(origen, dest, rel, aj_dict)
            hechos += 1
            if progreso:
                progreso(hechos, total)

    for enlace, objetivo in enlaces:
        enlace.parent.mkdir(parents=True, exist_ok=True)
        try:
            enlace.symlink_to(objetivo)
        except OSError:
            real = (base / enlace.relative_to(destino)).resolve()
            if real.exists():
                shutil.copy2(real, enlace)

    n_propios = _copiar_personalizados(destino, propios) if propios else 0
    (destino / "index.theme").write_text(_index_theme(base, destino.name), encoding="utf-8")
    marca.write_text(firma, encoding="utf-8")
    if progreso:
        progreso(total, total)
    return {"generado": True, "iconos": total + n_propios, "huella": firma}


def ajustes_desde_cfg(cfg: dict, paleta: dict[str, str], emblema: Path | None) -> Ajustes:
    tinte = cfg.get("tinte") or {}
    return Ajustes(
        glow=float(tinte.get("glow", 0)),
        objetivo=(tinte.get("objetivo") or paleta.get("bandera")
                  or paleta.get("primario", "#3584e4")),
        intensidad=float(tinte.get("intensidad", 0.85)),
        saturacion=float(tinte.get("saturacion", 1.0)),
        monocromo=bool(cfg.get("monocromo", False)),
        opacidad=float(cfg.get("opacidad", 1.0)),
        por_categoria=dict(tinte.get("por_categoria") or {}),
        emblema=str(emblema) if emblema and emblema.exists() else None,
        emblema_en=list(cfg.get("emblema_en") or ["places"]),
    )


def _main() -> None:  # pragma: no cover - uso manual
    import sys

    from ultron.nucleo import registro, rutas
    from ultron.ui.tema import cargar_tema

    modo = registro.obtener(sys.argv[1])
    cfg = modo.capas.get("iconos", {})
    emblema = modo.recurso(cfg["emblema"]) if cfg.get("emblema") else None
    aj = ajustes_desde_cfg(cfg, cargar_tema(modo.id).paleta, emblema)
    destino = rutas.xdg_datos_raiz() / "icons" / f"Ultron-{modo.id}"
    print(generar(modo.id, aj, destino,
                  dir_personalizados=modo.recurso(cfg.get("personalizados", "tema/iconos"))))


if __name__ == "__main__":  # pragma: no cover
    _main()
