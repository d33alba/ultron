"""Motor de temas de terminal: cada modo define paleta, bordes, glifos, banner y voz."""

from __future__ import annotations

import os
import random
import sys
import time
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

try:
    import tomllib
except ImportError:  # pragma: no cover
    import tomli as tomllib  # type: ignore[no-redef]

from rich import box
from rich.console import Console, RenderableType
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.theme import Theme

ESTILOS = ("primario", "secundario", "acento", "ok", "aviso", "error", "apagado", "texto")

GLIFOS_ASCII_DEFECTO = {
    "marca": "*", "ok": "+", "error": "x", "aviso": "!", "info": ">", "vineta": "-",
    "objetivo": "o", "flecha": ">", "barra_llena": "#", "barra_vacia": ".",
}

_BORDES = {
    "DOUBLE": box.DOUBLE, "ROUNDED": box.ROUNDED, "HEAVY": box.HEAVY,
    "SQUARE": box.SQUARE, "MINIMAL": box.MINIMAL, "SIMPLE": box.SIMPLE,
    "ASCII": box.ASCII, "NINGUNO": box.SIMPLE_HEAD,
}


@dataclass
class _Opciones:
    sin_animaciones: bool = False
    sin_color: bool = False


OPCIONES = _Opciones()


def configurar(sin_animaciones: bool = False, sin_color: bool = False) -> None:
    OPCIONES.sin_animaciones = sin_animaciones
    OPCIONES.sin_color = sin_color
    invalidar()


def soporta_unicode() -> bool:
    if os.environ.get("ULTRON_ASCII"):
        return False
    codificacion = (getattr(sys.stdout, "encoding", "") or "").lower()
    lang = (os.environ.get("LC_ALL") or os.environ.get("LANG") or "").lower()
    if lang in {"c", "posix"}:
        return False
    return "utf" in codificacion or "utf" in lang


def animaciones_activas() -> bool:
    if OPCIONES.sin_animaciones or os.environ.get("ULTRON_SIN_ANIMACIONES"):
        return False
    return bool(getattr(sys.stdout, "isatty", lambda: False)())


@dataclass
class Tema:
    id: str
    nombre: str
    paleta: dict[str, str]
    bordes: str = "ROUNDED"
    glifos: dict[str, str] = field(default_factory=dict)
    glifos_ascii: dict[str, str] = field(default_factory=dict)
    prompt: str = ""
    banner: str = ""
    banner_compacto: str = ""
    degradado: list[str] = field(default_factory=list)
    spinner: list[str] = field(default_factory=lambda: ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧"])
    entrada: str = "fundido"
    voz: dict[str, list[str]] = field(default_factory=dict)
    terminal: dict[str, Any] = field(default_factory=dict)
    _consola: Console | None = field(default=None, repr=False)

    # --- estilos -------------------------------------------------------------
    def estilo(self, nombre: str) -> str:
        return self.paleta.get(nombre, "")

    def theme(self) -> Theme:
        estilos = {n: self.paleta[n] for n in ESTILOS if self.paleta.get(n)}
        estilos.setdefault("texto", "default")
        # Rich no combina "bold" con nombres del tema: se registran las variantes.
        for nombre, color in list(estilos.items()):
            for mod in ("bold", "italic", "dim", "underline", "reverse"):
                estilos[f"{mod} {nombre}"] = f"{mod} {color}"
        return Theme(estilos, inherit=True)

    @property
    def caja(self) -> box.Box:
        if not soporta_unicode():
            return box.ASCII
        return _BORDES.get(self.bordes.upper(), box.ROUNDED)

    def glifo(self, nombre: str) -> str:
        if soporta_unicode():
            return self.glifos.get(nombre) or self.glifos_ascii.get(nombre, "")
        return self.glifos_ascii.get(nombre) or GLIFOS_ASCII_DEFECTO.get(nombre, "")

    def frase(self, tipo: str, defecto: str = "") -> str:
        frases = self.voz.get(tipo) or []
        return random.choice(frases) if frases else defecto

    # --- consola -------------------------------------------------------------
    @property
    def consola(self) -> Console:
        if self._consola is None:
            sin_color = OPCIONES.sin_color or bool(os.environ.get("NO_COLOR"))
            self._consola = Console(
                theme=self.theme(),
                color_system=None if sin_color else "auto",
                highlight=False,
                emoji=False,
            )
        return self._consola

    # --- componentes ---------------------------------------------------------
    def panel(self, contenido: RenderableType, titulo: str | None = None, **kw: Any) -> Panel:
        marca = self.glifo("marca")
        if titulo:
            titulo = f"[primario]{marca} {titulo}[/]" if marca else f"[primario]{titulo}[/]"
        return Panel(
            contenido, title=titulo, box=self.caja, border_style="primario",
            title_align="left", **kw,
        )

    def tabla(self, *columnas: str, titulo: str | None = None, **kw: Any) -> Table:
        t = Table(
            title=titulo, box=self.caja, border_style="primario", header_style="bold acento",
            title_style="bold primario", **kw,
        )
        for c in columnas:
            t.add_column(c)
        return t

    def _linea(self, glifo: str, estilo: str, msg: str) -> None:
        g = self.glifo(glifo)
        self.consola.print(f"[{estilo}]{g}[/] {msg}" if g else msg)

    def ok(self, msg: str) -> None:
        self._linea("ok", "ok", msg)

    def aviso(self, msg: str) -> None:
        self._linea("aviso", "aviso", msg)

    def error(self, msg: str) -> None:
        self._linea("error", "error", msg)

    def info(self, msg: str) -> None:
        self._linea("info", "acento", msg)

    def barra(self, fraccion: float, ancho: int = 20, estilo: str = "primario") -> Text:
        fraccion = max(0.0, min(1.0, fraccion))
        llenos = round(fraccion * ancho)
        lleno = self.glifo("barra_llena") or "█"
        vacio = self.glifo("barra_vacia") or "░"
        t = Text(lleno * llenos, style=estilo)
        t.append(vacio * (ancho - llenos), style="apagado")
        return t

    @contextmanager
    def spinner_ctx(self, texto: str) -> Iterator[None]:
        """Spinner con los fotogramas propios del modo."""
        if not animaciones_activas():
            self.consola.print(f"[apagado]{texto}…[/]")
            yield
            return
        fotogramas = self.spinner if soporta_unicode() else ["|", "/", "-", "\\"]

        class _Giro:
            def __rich__(self_inner) -> Text:  # noqa: N805
                i = int(time.monotonic() * 10) % len(fotogramas)
                return Text.assemble((fotogramas[i] + " ", "acento"), (texto, "texto"))

        with Live(_Giro(), console=self.consola, refresh_per_second=12, transient=True):
            yield

    # alias corto
    spinner_de = spinner_ctx


# --- carga -------------------------------------------------------------------

_cache: dict[str | None, Tema] = {}


def invalidar() -> None:
    _cache.clear()


def _ruta_tema(id_modo: str | None) -> Path:
    if id_modo:
        from ultron.nucleo import registro

        try:
            modo = registro.obtener(id_modo)
            ruta = modo.recurso("tema.toml")
            if ruta.exists():
                return ruta
        except Exception:  # noqa: BLE001 - se usa el tema por defecto
            pass
    return Path(__file__).with_name("tema_defecto.toml")


def desde_dict(datos: dict[str, Any], id_defecto: str = "ultron") -> Tema:
    return Tema(
        id=datos.get("id", id_defecto),
        nombre=datos.get("nombre", id_defecto.upper()),
        paleta=dict(datos.get("paleta", {})),
        bordes=datos.get("bordes", "ROUNDED"),
        glifos=dict(datos.get("glifos", {})),
        glifos_ascii=dict(datos.get("glifos_ascii", {})),
        prompt=datos.get("prompt", ""),
        banner=datos.get("banner", "").strip("\n"),
        banner_compacto=datos.get("banner_compacto", "").strip("\n"),
        degradado=list(datos.get("degradado", [])),
        spinner=list(datos.get("spinner", [])) or ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧"],
        entrada=datos.get("entrada", "fundido"),
        voz={k: list(v) for k, v in datos.get("voz", {}).items()},
        terminal=dict(datos.get("terminal", {})),
    )


def cargar_tema(id_modo: str | None = None) -> Tema:
    if id_modo in _cache:
        return _cache[id_modo]
    ruta = _ruta_tema(id_modo)
    with open(ruta, "rb") as f:
        datos = tomllib.load(f)
    tema = desde_dict(datos, id_modo or "ultron")
    _cache[id_modo] = tema
    return tema


def actual() -> Tema:
    """Tema del modo activo (o el de Ultron si no hay ninguno)."""
    from ultron.nucleo import estado

    return cargar_tema(estado.modo_activo())


def consola() -> Console:
    return actual().consola
