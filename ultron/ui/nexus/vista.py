"""Piezas visuales del NEXUS: holograma del fondo, letras grandes, reactor, barras y telemetría."""

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
    """El fondo del modo: el del tema, el generado o el de respaldo de la caché."""
    candidatos: list[Path] = []
    try:
        candidatos.append(modo.recurso("tema/fondo.png"))
    except Exception:  # noqa: BLE001
        pass
    for base in (rutas.datos(), rutas.cache()):
        if base.exists():
            candidatos += sorted(base.rglob(f"*{modo.id}*fondo*.png"))
            candidatos += sorted((base / "recursos" / modo.id).glob("fondo*.png"))
    return next((c for c in candidatos if c.exists()), None)


@lru_cache(maxsize=16)
def _miniatura(ruta: str, ancho: int, alto: int, mtime: float) -> list[list[tuple]]:
    from PIL import Image

    with Image.open(ruta) as img:
        img = img.convert("RGB").resize((ancho, alto * 2), Image.LANCZOS)
        px = img.load()
        return [[(px[x, y * 2], px[x, y * 2 + 1]) for x in range(ancho)] for y in range(alto)]


def holograma(modo: Any, paleta: dict[str, str], ancho: int, alto: int, t: float = 0.0) -> Text:
    """Miniatura del fondo en medios bloques, con una línea de escaneo que la recorre."""
    ruta = buscar_fondo(modo)
    filas: list[list[tuple]] | None = None
    if ruta is not None:
        try:
            filas = _miniatura(str(ruta), ancho, alto, ruta.stat().st_mtime)
        except Exception:  # noqa: BLE001
            filas = None
    if filas is None:
        filas = _rejilla(paleta, ancho, alto)
    barrido = int((t * 6) % (alto + 4)) - 2
    texto = Text()
    for y, fila in enumerate(filas):
        brillo = 0.35 if y == barrido else 0.0
        for arriba, abajo in fila:
            a = mezclar("#{:02X}{:02X}{:02X}".format(*arriba), paleta.get("primario", "#FFF"),
                        brillo)
            b = mezclar("#{:02X}{:02X}{:02X}".format(*abajo), paleta.get("primario", "#FFF"),
                        brillo)
            texto.append("▀", style=f"{a} on {b}")
        if y < alto - 1:
            texto.append("\n")
    return texto


def _rejilla(paleta: dict[str, str], ancho: int, alto: int) -> list[list[tuple]]:
    """Fondo de respaldo: degradado con rejilla de radar en los colores del modo."""
    fondo, prim = paleta.get("fondo", "#101418"), paleta.get("primario", "#00D7FF")
    cx, cy = ancho / 2, alto
    filas = []
    for y in range(alto):
        fila = []
        for x in range(ancho):
            par = []
            for sub in (0, 1):
                yy = y * 2 + sub
                d = math.hypot((x - cx) / ancho, (yy - cy) / (alto * 2))
                anillo = 0.5 if abs((d * 10) % 1 - 0.5) < 0.06 else 0.0
                rej = 0.25 if x % 8 == 0 or yy % 8 == 0 else 0.0
                par.append(_hex(mezclar(fondo, prim, max(anillo, rej) * (1 - d))))
            fila.append(tuple(par))
        filas.append(fila)
    return filas


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
