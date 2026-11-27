"""Piezas visuales del NEXUS: maqueta del escritorio, letras, reactor, barras, telemetría."""

from __future__ import annotations

import math
import socket
import time
from functools import lru_cache
from pathlib import Path
from typing import Any

from rich.text import Text

from ultron.nucleo import rutas

CHISPAS = "▁▂▃▄▅▆▇█"


def _hex(color: str, defecto: str = "#00D7FF") -> tuple[int, int, int]:
    c = (color or defecto).lstrip("#")
    if len(c) != 6:
        c = defecto.lstrip("#")
    return int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16)


def mezclar(a: str, b: str, t: float) -> str:
    ra, ga, ba = _hex(a)
    rb, gb, bb = _hex(b)
    t = max(0.0, min(1.0, t))
    r, g, b_ = (round(x + (y - x) * t) for x, y in ((ra, rb), (ga, gb), (ba, bb)))
    return f"#{r:02X}{g:02X}{b_:02X}"


def buscar_fondo(modo: Any) -> Path | None:
    """El fondo del modo: el del tema o el generado (sin recorrer carpetas: el NEXUS lo pide
    muchas veces y en ~/.local/share/ultron también viven Python y el Ojo de Dios)."""
    candidatos: list[Path] = []
    try:
        candidatos.append(modo.recurso("tema/fondo.png"))
    except Exception:  # noqa: BLE001
        pass
    for base in (rutas.datos(), rutas.cache()):
        candidatos += [base / "recursos" / modo.id / "fondo.png",
                       base / "fondos" / f"{modo.id}-fondo.png"]
    return next((c for c in candidatos if c.is_file()), None)


MOSAICO = (16, 8)  # colores de muestra del fondo (columnas, filas)


def colores_fondo(ruta: Path) -> list[list[str]] | None:
    """Mosaico de 16x8 colores del fondo, guardado en disco: el PNG (5-9 MB) solo se abre
    una vez por modo y versión del archivo."""
    import json

    try:
        clave = f"{ruta}|{ruta.stat().st_mtime_ns}"
    except OSError:
        return None
    cache = rutas.cache() / "nexus-mosaicos.json"
    try:
        datos = json.loads(cache.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        datos = {}
    if clave in datos:
        return datos[clave]
    try:
        from PIL import Image

        with Image.open(ruta) as img:
            img.draft("RGB", (256, 144))
            peque = img.convert("RGB").resize(MOSAICO, Image.BOX)
            px = peque.load()
            mosaico = [["#{:02X}{:02X}{:02X}".format(*px[x, y]) for x in range(MOSAICO[0])]
                       for y in range(MOSAICO[1])]
    except Exception:  # noqa: BLE001
        return None
    datos = {k: v for k, v in datos.items() if not k.startswith(f"{ruta}|")}
    datos[clave] = mosaico
    try:
        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_text(json.dumps(datos), encoding="utf-8")
    except OSError:
        pass
    return mosaico


BANDAS = 32  # tramos de color por fila: suave a la vista y pocas piezas para Textual


@lru_cache(maxsize=32)
def _degradado(mosaico: tuple[tuple[str, ...], ...], alto: int) -> list[list[str]]:
    """Interpola el mosaico de colores (bilineal) en `alto` filas de BANDAS tramos: se ve
    como el fondo difuminado, sin cuadros."""
    mf, mc = len(mosaico), len(mosaico[0])
    rgb = [[_hex(c) for c in fila] for fila in mosaico]

    def muestra(fx: float, fy: float) -> str:
        x, y = fx * (mc - 1), fy * (mf - 1)
        x0, y0 = int(x), int(y)
        x1, y1 = min(mc - 1, x0 + 1), min(mf - 1, y0 + 1)
        tx, ty = x - x0, y - y0
        canal = [
            (rgb[y0][x0][i] * (1 - tx) + rgb[y0][x1][i] * tx) * (1 - ty)
            + (rgb[y1][x0][i] * (1 - tx) + rgb[y1][x1][i] * tx) * ty
            for i in range(3)
        ]
        return "#{:02X}{:02X}{:02X}".format(*(round(v) for v in canal))

    return [[muestra((b + 0.5) / BANDAS, y / max(1, alto - 1)) for b in range(BANDAS)]
            for y in range(alto)]


def _partir(texto: str, ancho: int) -> list[str]:
    """Parte un título en líneas de `ancho` como mucho (por palabras)."""
    lineas, actual = [], ""
    for palabra in texto.split():
        if actual and len(actual) + 1 + len(palabra) > ancho:
            lineas.append(actual)
            actual = palabra
        else:
            actual = f"{actual} {palabra}".strip()
    if actual:
        lineas.append(actual)
    return [linea[:ancho] for linea in lineas] or [""]


def _celdas_a_texto(celdas: list[list[tuple[str, str, str]]]) -> Text:
    """Une las celdas con el mismo estilo en tramos: pocas piezas para Textual = fluido."""
    texto = Text()
    for y, fila in enumerate(celdas):
        tramo, estilo = "", None
        for car, fg, bg in fila:
            st = f"{fg} on {bg}"
            if st != estilo and tramo:
                texto.append(tramo, style=estilo)
                tramo = ""
            tramo += car
            estilo = st
        if tramo:
            texto.append(tramo, style=estilo)
        if y < len(celdas) - 1:
            texto.append("\n")
    return texto


def maqueta(modo: Any, paleta: dict[str, str], ancho: int, alto: int, t: float = 0.0,
            funciones: list[tuple[str, str]] | None = None) -> Text:
    """Maqueta viva del escritorio que vas a tener: colores del fondo, barra superior, dock
    en su sitio real, columna de funciones, y si hay música y voz. Barata de dibujar."""
    prim = paleta.get("primario", "#00D7FF")
    acento = paleta.get("acento", prim)
    texto_c = paleta.get("texto", "#E6E6E6")
    fondo_p = paleta.get("fondo", "#0B0F14")
    ruta = buscar_fondo(modo)
    mosaico = colores_fondo(ruta) if ruta else None
    if not mosaico:
        mosaico = [[fondo_p, mezclar(fondo_p, prim, 0.3)], [mezclar(fondo_p, prim, 0.12), fondo_p]]
    barrido = int((t * 5) % (alto + 6)) - 3
    filas = _degradado(tuple(map(tuple, mosaico)), alto)

    def color_fondo(x: int, y: int) -> str:
        base = filas[y][min(BANDAS - 1, x * BANDAS // ancho)]
        return mezclar(base, prim, 0.18) if y == barrido else base

    celdas = [[(" ", texto_c, color_fondo(x, y)) for x in range(ancho)] for y in range(alto)]

    def escribir(x: int, y: int, cadena: str, fg: str, bg: str | None = None) -> None:
        for i, car in enumerate(cadena):
            if 0 <= x + i < ancho and 0 <= y < alto:
                celdas[y][x + i] = (car, fg, bg or celdas[y][x + i][2])

    capas = getattr(modo, "capas", {}) or {}
    esc = capas.get("escritorio") or {}
    dock = esc.get("dock") or {}
    # barra superior
    barra_bg = mezclar(fondo_p, "#000000", 0.35)
    escribir(0, 0, " " * ancho, texto_c, barra_bg)
    escribir(1, 0, f"◆ {getattr(modo, 'nombre', '')}", prim, barra_bg)
    reloj = time.strftime("%H:%M")
    escribir(max(0, ancho - len(reloj) - 6), 0, f"{reloj}  ◖◗", texto_c, barra_bg)
    # dock
    fn = funciones or []
    dock_bg = dock.get("background-color") or mezclar(fondo_p, prim, 0.25)
    oculto = bool(dock.get("autohide")) and not dock.get("dock-fixed")
    iconos = [ic for ic, _ in fn][:8] or ["◆"]
    izq = str(dock.get("dock-position", "BOTTOM")).upper() == "LEFT"
    margen_x = 1
    if izq and not oculto:
        alto_dock = alto - 1 if dock.get("extend-height") else min(alto - 2, len(iconos) * 2 + 1)
        y0 = 1 if dock.get("extend-height") else max(1, (alto - alto_dock) // 2)
        for y in range(y0, y0 + alto_dock):
            escribir(0, y, "   ", texto_c, dock_bg)
        for i, ic in enumerate(iconos):
            escribir(1, y0 + 1 + i * 2, ic, "#FFFFFF", dock_bg)
        margen_x = 5
    elif not oculto:
        tira = " " + "  ".join(iconos) + " "
        x0 = max(0, (ancho - len(tira)) // 2)
        escribir(x0, alto - 1, tira, "#FFFFFF", dock_bg)
    else:
        escribir(max(0, ancho // 2 - 7), alto - 1, "▁▁ dock oculto ▁▁",
                 mezclar(texto_c, fondo_p, 0.4), None)
    # iconos del escritorio: losetas con su nombre debajo, como en el escritorio real
    paso_x, paso_y = 12, 4
    por_fila = max(1, (ancho - margen_x - 2) // paso_x)
    for i, (ic, titulo) in enumerate(fn):
        col, fila = i % por_fila, i // por_fila
        x, y = margen_x + 1 + col * paso_x, 2 + fila * paso_y
        if y + 2 >= alto - 2:
            break
        escribir(x + 3, y, f" {ic} ", fondo_p, prim)
        for j, linea in enumerate(_partir(titulo, paso_x - 2)[:2]):
            escribir(x + (paso_x - 1 - len(linea)) // 2, y + 1 + j, linea, "#FFFFFF")
    # insignias: música y voz
    insignias = []
    if capas.get("musica"):
        insignias.append("♪ música")
    insignias.append("◉ voz")
    chapa = "  ".join(insignias)
    escribir(max(0, ancho - len(chapa) - 2), alto - 2, f" {chapa} ", fondo_p, acento)
    return _celdas_a_texto(celdas)


def letras_grandes(texto: str, color: str, color2: str | None = None) -> Text:
    from ultron.modos.presentacion.letras import grandes

    filas = grandes(texto)
    salida = Text()
    for i, fila in enumerate(filas):
        tono = mezclar(color, color2 or color, i / max(1, len(filas) - 1))
        salida.append(fila, style=f"bold {tono}")
        if i < len(filas) - 1:
            salida.append("\n")
    return salida


def reactor(t: float, color: str, apagado: str, radio: int = 7) -> Text:
    """Núcleo tipo reactor que gira: anillos concéntricos con segmentos animados."""
    alto, ancho = radio * 2 + 1, radio * 4 + 1
    texto = Text()
    for fy in range(alto):
        for fx in range(ancho):
            dx, dy = (fx - radio * 2) / 2, fy - radio
            d = math.hypot(dx, dy)
            ang = (math.atan2(dy, dx) + math.pi) / (2 * math.pi)
            if d < 1.2:
                texto.append("◆", style=f"bold {color}")
            elif abs(d - radio * 0.45) < 0.5:
                on = int((ang + t * 0.8) * 12) % 2 == 0
                texto.append("●" if on else "·", style=color if on else apagado)
            elif abs(d - radio * 0.8) < 0.5:
                on = int((ang - t * 0.5) * 24) % 3 != 0
                texto.append("━" if abs(dx) > abs(dy) else "┃", style=color if on else apagado)
            else:
                texto.append(" ")
        if fy < alto - 1:
            texto.append("\n")
    return texto


def barra(valor: float, ancho: int, color: str, apagado: str) -> Text:
    valor = max(0.0, min(1.0, valor))
    llenas = round(valor * ancho)
    t = Text()
    t.append("▰" * llenas, style=color)
    t.append("▱" * (ancho - llenas), style=apagado)
    return t


def chispas(valores: list[float], ancho: int) -> str:
    vals = valores[-ancho:]
    if not vals:
        return ""
    tope = max(max(vals), 1e-9)
    return "".join(CHISPAS[min(7, int(v / tope * 7.99))] for v in vals)


class Telemetria:
    """Lee CPU, RAM, disco, red y batería con psutil, sin bloquear la interfaz."""

    def __init__(self) -> None:
        self.cpu: list[float] = []
        self.red: list[float] = []
        self._red_prev: tuple[float, float] | None = None
        try:
            import psutil

            self.ps = psutil
            psutil.cpu_percent(None)
        except Exception:  # noqa: BLE001
            self.ps = None

    def muestra(self) -> dict[str, Any]:
        datos: dict[str, Any] = {"host": socket.gethostname()}
        if self.ps is None:
            return datos
        ps = self.ps
        cpu = ps.cpu_percent(None)
        self.cpu = (self.cpu + [cpu])[-60:]
        datos["cpu"] = cpu / 100
        datos["ram"] = ps.virtual_memory().percent / 100
        try:
            datos["disco"] = ps.disk_usage(str(Path.home())).percent / 100
        except Exception:  # noqa: BLE001
            datos["disco"] = 0.0
        io = ps.net_io_counters()
        ahora = (time.monotonic(), float(io.bytes_recv + io.bytes_sent))
        if self._red_prev:
            dt = max(1e-3, ahora[0] - self._red_prev[0])
            self.red = (self.red + [(ahora[1] - self._red_prev[1]) / dt])[-60:]
        self._red_prev = ahora
        datos["red_kbs"] = (self.red[-1] / 1024) if self.red else 0.0
        bat = ps.sensors_battery() if hasattr(ps, "sensors_battery") else None
        datos["bateria"] = None if bat is None else bat.percent / 100
        datos["uptime_h"] = (time.time() - ps.boot_time()) / 3600
        datos["procesos"] = len(ps.pids())
        return datos


def ip_local() -> str:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("10.255.255.255", 1))
            return s.getsockname()[0]
    except OSError:
        return "sin red"
