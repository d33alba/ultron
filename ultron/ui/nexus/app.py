"""NEXUS: el centro de mando de Ultron a pantalla completa (Textual).

Tres pantallas: ARRANQUE (núcleo que se enciende), HANGAR (elegir modo con su holograma) y
PUENTE (el modo activo: telemetría, fichas de funciones y una barra donde se escribe lo que se
quiere en lenguaje natural). Todo se maneja con flechas, Enter o el ratón; ninguna función
exige saberse un comando. La app devuelve qué ejecutar y `nexus.abrir()` lo lanza en la propia
terminal y vuelve aquí al acabar.
"""

from __future__ import annotations

import time
from datetime import datetime
from typing import Any

from rich.text import Text
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Grid, Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen, Screen
from textual.widgets import Button, Checkbox, DirectoryTree, Input, OptionList, Static
from textual.widgets.option_list import Option

from ultron import __version__
from ultron.nucleo import estado, registro
from ultron.ui import tema as temas
from ultron.ui.nexus import catalogo, vista
from ultron.ui.nexus.catalogo import Ficha

NOMBRES_CAPA = {
    "shell": "Prompt, alias y bienvenida de la terminal",
    "terminal": "Colores, fuente y transparencia de la terminal",
    "escritorio": "Fondo, tema de ventanas y barra superior",
    "iconos": "Iconos de carpetas, archivos y aplicaciones",
    "cursor": "Cursor del ratón",
    "fuentes": "Tipografías del sistema",
    "extensiones": "Animaciones y efectos de ventanas",
    "sistema": "Notificaciones, energía y webs bloqueadas",
    "sonido": "Sonidos del sistema",
    "musica": "Música de fondo",
    "widgets": "Widgets en vivo sobre el escritorio",
    "arranque": "Pantalla de arranque y de inicio de sesión",
    "lanzadores": "Funciones en el escritorio, el dock y el menú",
    "disposicion": "Disposición: dock, barra y escritorio",
}

TRUCOS = {
    "netanyahu": ["Escribe «investiga ubuntu.com» o «escanea mi red».",
                  "En el panel superior, el ◆ abre todas las operaciones.",
                  "Suelta una foto en «Metadatos» del escritorio y verás su GPS."],
    "focus": ["Escribe «resume tema3.pdf» o «examen».",
              "Arrastra un PDF al icono «Resumir apuntes» del escritorio.",
              "Clic derecho en un PDF → Scripts → Ultron → Flashcards."],
    "gaming": ["Escribe «turbo» antes de jugar.", "Super+U abre el NEXUS desde cualquier sitio.",
               "El HUD muestra temperaturas en directo."],
    "presentacion": ["Escribe «presentar» y elige tu .md.",
                     "El cronómetro se ve desde el fondo del aula."],
    "fantasma": ["Escribe «borra rastros» al terminar.",
                 "Suelta una foto en «Quitar metadatos» antes de compartirla."],
}


def paleta(id_modo: str | None) -> dict[str, str]:
    base = {"primario": "#00D7FF", "acento": "#7FDBFF", "texto": "#E0E0E0", "apagado": "#808080",
            "fondo": "#101418", "ok": "#4CD964", "aviso": "#FFCC00", "error": "#FF3B30"}
    try:
        base.update({k: v for k, v in temas.cargar_tema(id_modo or "ultron").paleta.items()
                     if isinstance(v, str) and v.startswith("#")})
    except Exception:  # noqa: BLE001
        pass
    base["panel"] = vista.mezclar(base["fondo"], base["primario"], 0.08)
    base["borde"] = vista.mezclar(base["fondo"], base["primario"], 0.35)
    return base


def glifo_modo(id_modo: str) -> str:
    try:
        return temas.cargar_tema(id_modo).glifo("marca") or "◆"
    except Exception:  # noqa: BLE001
        return "◆"


def estado_ia() -> tuple[bool, str]:
    try:
        from ultron.ia.ajustes import resolver

        aj = resolver(autodetectar=False)
    except Exception:  # noqa: BLE001
        aj = None
    if aj is None:
        return False, "IA sin configurar"
    host = aj.url_base.split("//")[-1].split("/")[0]
    return True, f"{aj.modelo or 'IA'} @ {host}"


# ── widgets ─────────────────────────────────────────────────────────────────────


class Tarjeta(Static, can_focus=True):
    """Una función como tarjeta: icono, título y descripción. Enter o clic la abre."""

    def __init__(self, ficha: Ficha, p: dict[str, str]) -> None:
        super().__init__(classes="tarjeta")
        self.ficha = ficha
        self.p = p

    def on_mount(self) -> None:
        p, f = self.p, self.ficha
        t = Text()
        t.append(f" {f.icono} ", style=f"bold {p['fondo']} on {p['primario']}")
        t.append(f"  {f.titulo}\n", style=f"bold {p['texto']}")
        t.append(f.descripcion, style=p["apagado"])
        self.update(t)

    def on_click(self) -> None:
        self.screen.abrir_ficha(self.ficha)  # type: ignore[attr-defined]

    def on_key(self, evento: Any) -> None:
        if evento.key == "enter":
            evento.stop()
            self.screen.abrir_ficha(self.ficha)  # type: ignore[attr-defined]
        elif evento.key in ("up", "down", "left", "right"):
            evento.stop()
            self.screen.mover_foco(self, evento.key)  # type: ignore[attr-defined]
        elif evento.character and evento.character.isprintable() and evento.character != " " \
                and len(evento.character) == 1 and evento.key not in ("q", "m", "s", "slash"):
            evento.stop()
            mando = self.screen.query_one("#mando", Input)
            mando.focus()
            mando.value += evento.character
            mando.cursor_position = len(mando.value)


# ── pantallas ───────────────────────────────────────────────────────────────────


class Arranque(Screen):
    """El núcleo se enciende mientras se comprueba el sistema (cualquier tecla lo salta)."""

    def __init__(self, siguiente: Screen, p: dict[str, str]) -> None:
        super().__init__()
        self.siguiente, self.p, self.t0 = siguiente, p, time.monotonic()
        self.lineas = self._comprobaciones()

    def _comprobaciones(self) -> list[tuple[str, str, bool]]:
        filas: list[tuple[str, str, bool]] = [("Núcleo ULTRON", f"v{__version__}", True)]
        try:
            from ultron.nucleo.entorno import detectar

            e = detectar()
            filas.append(("Sistema", f"{e.distro} {e.version}".strip() or e.so, True))
            filas.append(("Escritorio", f"GNOME {e.gnome or '—'} · {e.sesion or '—'}",
                          bool(e.gnome)))
        except Exception:  # noqa: BLE001
            pass
        ok, ia = estado_ia()
        filas.append(("Inteligencia", ia, ok))
        filas.append(("Modos cargados", str(len(registro.listar())), True))
        activo = estado.modo_activo()
        filas.append(("Modo activo", activo.upper() if activo else "ninguno", True))
        return filas

    def compose(self) -> ComposeResult:
        yield Static(id="reactor")
        yield Static(id="log")

    def on_mount(self) -> None:
        self.styles.background = self.p["fondo"]
        self.set_interval(1 / 24, self.pintar)
        from ultron.nucleo import voz

        voz.hablar("Ultron en línea. Todos los sistemas operativos.")

    def pintar(self) -> None:
        t = time.monotonic() - self.t0
        p = self.p
        self.query_one("#reactor", Static).update(vista.reactor(t * 3, p["primario"],
                                                                p["borde"]))
        log = Text()
        visibles = int(t / 0.22)
        for nombre, valor, ok in self.lineas[:visibles]:
            log.append("  ▸ ", style=p["primario"])
            log.append(f"{nombre:<16}", style=p["texto"])
            log.append(f"{valor:<34}", style=p["acento"])
            log.append("[ OK ]\n" if ok else "[ -- ]\n", style=p["ok"] if ok else p["aviso"])
        if visibles > len(self.lineas):
            log.append("\n  SISTEMAS EN LÍNEA · BIENVENIDO", style=f"bold {p['primario']}")
        self.query_one("#log", Static).update(log)
        if t > 0.22 * len(self.lineas) + 0.9:
            self.app.switch_screen(self.siguiente)

    def on_key(self) -> None:
        self.app.switch_screen(self.siguiente)

    def on_click(self) -> None:
        self.app.switch_screen(self.siguiente)


class Hangar(Screen):
    """Elegir modo: lista, holograma del escritorio que vas a tener y qué cambia."""

    BINDINGS = [
        Binding("enter", "activar", "Activar"), Binding("s", "restaurar", "Restaurar Ubuntu"),
        Binding("c", "configurar", "Configurar IA"), Binding("escape,q", "cerrar", "Cerrar"),
        Binding("tab", "puente", "Puente", show=False),
    ]

    def __init__(self) -> None:
        super().__init__()
        self.modos = registro.listar()
        self.activo = estado.modo_activo()
        ids = [m.id for m in self.modos]
        self.indice = ids.index(self.activo) if self.activo in ids else 0
        self.t0 = time.monotonic()

    def compose(self) -> ComposeResult:
        yield Static(id="cabecera")
        with Horizontal(id="cuerpo"):
            with Vertical(id="col-modos"):
                yield Static("  MODOS", classes="titulo")
                yield OptionList(*[Option(self._etiqueta(m), id=m.id) for m in self.modos],
                                 id="modos")
            with Vertical(id="col-holo"):
                yield Static(id="holo")
                yield Static(id="nombre")
            with VerticalScroll(id="col-info"):
                yield Static(id="info")
        with Horizontal(id="botones"):
            yield Button("⏎  ACTIVAR MODO", id="activar", variant="primary")
            yield Button("↺  Restaurar Ubuntu", id="restaurar")
            yield Button("⚙  Configurar IA", id="configurar")
            yield Button("✕  Cerrar", id="cerrar")
        yield Static(id="pie")

    def _etiqueta(self, m: Any) -> Text:
        p = paleta(m.id)
        t = Text()
        t.append(f" {glifo_modo(m.id)} ", style=f"bold {p['primario']}")
        t.append(m.nombre, style="bold")
        if m.id == self.activo:
            t.append("  ● activo", style=p["ok"])
        t.append(f"\n   {m.lema}", style=p["apagado"])
        return t

    def on_mount(self) -> None:
        lista = self.query_one("#modos", OptionList)
        lista.highlighted = self.indice
        lista.focus()
        self.pintar()
        self.set_interval(1 / 10, self.animar)

    def on_option_list_option_highlighted(self, evento: OptionList.OptionHighlighted) -> None:
        self.indice = evento.option_index
        self.t0 = time.monotonic()
        self.pintar()

    def on_option_list_option_selected(self, evento: OptionList.OptionSelected) -> None:
        self.indice = evento.option_index
        self.action_activar()

    def on_button_pressed(self, evento: Button.Pressed) -> None:
        getattr(self, f"action_{evento.button.id}")()

    def animar(self) -> None:
        m = self.modos[self.indice]
        p = paleta(m.id)
        holo = self.query_one("#holo", Static)
        ancho = max(20, min(120, holo.content_size.width or 60))
        alto = max(6, min(36, holo.content_size.height or 14))
        holo.update(vista.holograma(m, p, ancho, alto, time.monotonic() - self.t0))
        reloj = datetime.now().strftime("%H:%M:%S")
        ok, ia = estado_ia()
        cab = Text()
        cab.append(" ◆ U L T R O N ", style=f"bold {p['fondo']} on {p['primario']}")
        cab.append("  N E X U S ", style=f"bold {p['primario']}")
        cab.append(f"   elige en quién se convierte tu ordenador{' ' * 6}",
                   style=p["apagado"])
        cab.append(f"● {ia}   " if ok else f"○ {ia} (pulsa c)   ",
                   style=p["ok"] if ok else p["aviso"])
        cab.append(reloj, style=f"bold {p['texto']}")
        self.query_one("#cabecera", Static).update(cab)

    def pintar(self) -> None:
        m = self.modos[self.indice]
        p = paleta(m.id)
        self.styles.background = p["fondo"]
        for sel in ("#col-modos", "#col-info", "#holo"):
            w = self.query_one(sel)
            w.styles.border = ("round", p["borde"])
            w.styles.background = p["panel"]
        self.query_one("#holo").styles.border = ("heavy", p["primario"])
        nombre = Text(justify="center")
        nombre.append_text(vista.letras_grandes(m.nombre, p["primario"], p["acento"]))
        nombre.append(f"\n\n«{m.lema}»\n", style=f"italic {p['acento']}")
        nombre.append(m.descripcion, style=p["texto"])
        self.query_one("#nombre", Static).update(nombre)
        self.query_one("#info", Static).update(self._info(m, p))
        for b in self.query(Button):
            b.styles.background = p["primario"] if b.id == "activar" else p["panel"]
            b.styles.color = p["fondo"] if b.id == "activar" else p["texto"]
            b.styles.border = ("tall", p["primario"] if b.id == "activar" else p["borde"])
        pie = Text()
        for tecla, que in (("↑↓", "elegir"), ("⏎", "activar"), ("s", "restaurar Ubuntu"),
                           ("c", "IA"), ("tab", "puente del modo activo"), ("q", "cerrar")):
            pie.append(f" {tecla} ", style=f"bold {p['fondo']} on {p['acento']}")
            pie.append(f" {que}   ", style=p["apagado"])
        self.query_one("#pie", Static).update(pie)
        self.animar()

    def _info(self, m: Any, p: dict[str, str]) -> Text:
        t = Text()
        t.append("AL ACTIVARLO CAMBIA\n", style=f"bold {p['primario']}")
        capas = list(m.capas.keys())
        if "lanzadores" not in capas:
            capas.append("lanzadores")
        for capa in capas:
            if capa in ("fuentes",):
                continue
            t.append(" ✔ ", style=p["ok"])
            t.append(f"{NOMBRES_CAPA.get(capa, capa)}\n", style=p["texto"])
        t.append("\nFUNCIONES\n", style=f"bold {p['primario']}")
        for f in catalogo.de_modo(m.id)[:9]:
            t.append(f" {f.icono} ", style=p["acento"])
            t.append(f"{f.titulo}\n", style=p["texto"])
        t.append("\nTodo se deshace con «Restaurar Ubuntu».", style=p["apagado"])
        return t

    def action_activar(self) -> None:
        self.app.exit(("entrar", self.modos[self.indice].id))

    def action_restaurar(self) -> None:
        self.app.exit(("ejecutar", ["salir"]))

    def action_configurar(self) -> None:
        self.app.exit(("ejecutar", ["ia", "configurar"]))

    def action_cerrar(self) -> None:
        self.app.exit(None)

    def action_puente(self) -> None:
        if self.activo:
            self.app.switch_screen(Puente(self.activo))


class Puente(Screen):
    """Centro de mando del modo activo."""

    BINDINGS = [
        Binding("tab", "hangar", "Modos"), Binding("ctrl+r", "restaurar", "Restaurar"),
        Binding("escape", "limpiar", "Limpiar o cerrar"),
    ]

    def __init__(self, id_modo: str | None, aviso: str = "") -> None:
        super().__init__()
        self.id_modo = id_modo
        self.modo = registro.obtener(id_modo) if id_modo else None
        self.p = paleta(id_modo)
        self.tele = vista.Telemetria()
        self.aviso = aviso
        self.otras = [f for f in catalogo.FICHAS if f.modo not in (id_modo, catalogo.COMUN)]
        self.fichas = catalogo.de_modo(id_modo) + catalogo.comunes() + self.otras

    def compose(self) -> ComposeResult:
        yield Static(id="cabecera")
        yield Input(placeholder="▸ Escribe lo que necesitas… («resume mis apuntes», "
                                "«escanea mi red», «pon música») y pulsa Enter", id="mando",
                    select_on_focus=False)
        with Horizontal(id="cuerpo"):
            yield Static(id="telemetria")
            with VerticalScroll(id="centro"):
                if self.aviso:
                    yield Static(self.aviso, id="aviso")
                nombre = self.modo.nombre if self.modo else "ULTRON"
                yield Static(f"  FUNCIONES {nombre}", classes="titulo", id="t-modo")
                with Grid(classes="rejilla", id="rejilla-modo"):
                    for f in catalogo.de_modo(self.id_modo):
                        yield Tarjeta(f, self.p)
                yield Static("  HERRAMIENTAS DE SIEMPRE", classes="titulo")
                with Grid(classes="rejilla", id="rejilla-comun"):
                    for f in catalogo.comunes():
                        yield Tarjeta(f, self.p)
                yield Static("  DE OTROS MODOS", classes="titulo", id="t-otros")
                with Grid(classes="rejilla", id="rejilla-otros"):
                    for f in self.otras:
                        yield Tarjeta(f, self.p)
            yield Static(id="intel")
        yield Static(id="pie")

    def on_mount(self) -> None:
        p = self.p
        self.styles.background = p["fondo"]
        for sel in ("#telemetria", "#intel", "#centro"):
            w = self.query_one(sel)
            w.styles.border = ("round", p["borde"])
            w.styles.background = p["panel"]
        mando = self.query_one("#mando", Input)
        mando.styles.border = ("tall", p["primario"])
        mando.styles.background = p["panel"]
        mando.styles.color = p["texto"]
        for t in self.query(".titulo"):
            t.styles.color = p["primario"]
        for t in self.query(Tarjeta):
            t.styles.border = ("round", p["borde"])
        self._pie()
        self.on_input_changed(Input.Changed(self.query_one("#mando", Input), ""))
        self.refrescar()
        self.set_interval(1.0, self.refrescar)
        tarjetas = list(self.query(Tarjeta))
        if tarjetas:
            tarjetas[0].focus()

    def on_descendant_focus(self, evento: Any) -> None:
        for t in self.query(Tarjeta):
            foco = t is evento.widget
            t.styles.border = ("heavy" if foco else "round",
                               self.p["primario"] if foco else self.p["borde"])
            t.styles.background = vista.mezclar(self.p["panel"], self.p["primario"],
                                                0.15) if foco else self.p["panel"]

    def _pie(self) -> None:
        p = self.p
        pie = Text()
        for tecla, que in (("←↑↓→", "moverse"), ("⏎", "abrir"), ("escribe", "buscar o pedir"),
                           ("tab", "cambiar de modo"), ("ctrl+r", "restaurar Ubuntu"),
                           ("esc", "cerrar")):
            pie.append(f" {tecla} ", style=f"bold {p['fondo']} on {p['acento']}")
            pie.append(f" {que}   ", style=p["apagado"])
        self.query_one("#pie", Static).update(pie)

    def refrescar(self) -> None:
        p = self.p
        d = self.tele.muestra()
        ok, ia = estado_ia()
        cab = Text()
        marca = glifo_modo(self.id_modo) if self.id_modo else "◆"
        nombre = self.modo.nombre if self.modo else "ULTRON"
        cab.append(f" {marca} {nombre} ", style=f"bold {p['fondo']} on {p['primario']}")
        cab.append("  NEXUS", style=f"bold {p['primario']}")
        if self.modo:
            cab.append(f"  ·  {self.modo.lema}", style=f"italic {p['acento']}")
        cab.append("     ")
        cab.append(f"● {ia}" if ok else f"○ {ia}", style=p["ok"] if ok else p["aviso"])
        ahora = datetime.now()
        dia = ("lunes", "martes", "miércoles", "jueves", "viernes", "sábado",
               "domingo")[ahora.weekday()]
        cab.append(f"     {dia} {ahora:%d} · {ahora:%H:%M:%S}",
                   style=f"bold {p['texto']}")
        self.query_one("#cabecera", Static).update(cab)
        self.query_one("#telemetria", Static).update(self._telemetria(d))
        self.query_one("#intel", Static).update(self._intel())

    def _telemetria(self, d: dict[str, Any]) -> Text:
        p = self.p
        t = Text()
        t.append("TELEMETRÍA\n\n", style=f"bold {p['primario']}")
        for clave, nombre in (("cpu", "CPU"), ("ram", "RAM"), ("disco", "DISCO"),
                              ("bateria", "BATERÍA")):
            valor = d.get(clave)
            if valor is None:
                continue
            nivel = 1 - valor if clave == "bateria" else valor
            color = p["error"] if nivel > 0.85 else (p["aviso"] if nivel > 0.6 else p["ok"])
            t.append(f"{nombre:<8}", style=p["texto"])
            t.append_text(vista.barra(valor, 12, color, p["borde"]))
            t.append(f" {valor * 100:3.0f}%\n", style=color)
        if self.tele.cpu:
            t.append("\nCPU 60 s\n", style=p["apagado"])
            t.append(vista.chispas(self.tele.cpu, 24) + "\n", style=p["primario"])
        if self.tele.red:
            t.append(f"RED {d.get('red_kbs', 0):7.1f} KB/s\n", style=p["apagado"])
            t.append(vista.chispas(self.tele.red, 24) + "\n", style=p["acento"])
        t.append(f"\nEQUIPO  {d.get('host', '')}\n", style=p["apagado"])
        t.append(f"IP      {vista.ip_local()}\n", style=p["apagado"])
        if "uptime_h" in d:
            t.append(f"ACTIVO  {d['uptime_h']:.1f} h · {d.get('procesos', 0)} procesos\n",
                     style=p["apagado"])
        return t

    def _intel(self) -> Text:
        p = self.p
        t = Text()
        t.append("INTEL\n\n", style=f"bold {p['primario']}")
        for linea in info_modo(self.id_modo):
            t.append(" ▸ ", style=p["acento"])
            t.append(linea + "\n", style=p["texto"])
        t.append("\nTRUCOS\n", style=f"bold {p['primario']}")
        for truco in TRUCOS.get(self.id_modo or "", ["Escribe lo que quieras hacer."]):
            t.append(" ✦ ", style=p["acento"])
            t.append(truco + "\n", style=p["apagado"])
        t.append("\nEN TU ESCRITORIO\n", style=f"bold {p['primario']}")
        for linea in ("Funciones en el dock y el escritorio", "Menú ◆ de la barra superior",
                      "Super+U abre el NEXUS"):
            t.append(" ◆ ", style=p["acento"])
            t.append(linea + "\n", style=p["apagado"])
        return t

    # --- búsqueda y navegación -------------------------------------------------
    def on_input_changed(self, evento: Input.Changed) -> None:
        consulta = evento.value.strip()
        orden = catalogo.ordenar_por_consulta(self.fichas, consulta) if consulta else None
        visibles = set(map(id, orden)) if orden is not None else None
        for t in self.query(Tarjeta):
            otra = t.ficha.modo not in (self.id_modo, catalogo.COMUN)
            t.display = (not otra) if visibles is None else id(t.ficha) in visibles
        hay_otras = visibles is not None and any(id(f) in visibles for f in self.otras)
        self.query_one("#t-otros").display = hay_otras
        self.query_one("#rejilla-otros").display = hay_otras

    def on_input_submitted(self, evento: Input.Submitted) -> None:
        consulta = evento.value.strip()
        if not consulta:
            return
        orden = catalogo.ordenar_por_consulta(self.fichas, consulta)
        if orden and catalogo.puntuar(orden[0], consulta) >= 1.5:
            self.abrir_ficha(orden[0], consulta)
        else:
            self.app.push_screen(PedirIA(consulta, self.p))

    def mover_foco(self, actual: Tarjeta, tecla: str) -> None:
        tarjetas = [t for t in self.query(Tarjeta) if t.display]
        if actual not in tarjetas:
            return
        i = tarjetas.index(actual)
        columnas = max(1, (self.query_one("#centro").size.width - 2) // 34)
        delta = {"left": -1, "right": 1, "up": -columnas, "down": columnas}[tecla]
        j = i + delta
        if j < 0 and tecla == "up":
            self.query_one("#mando", Input).focus()
            return
        tarjetas[max(0, min(len(tarjetas) - 1, j))].focus()

    def on_key(self, evento: Any) -> None:
        mando = self.query_one("#mando", Input)
        if evento.key == "down" and mando.has_focus:
            evento.stop()
            visibles = [t for t in self.query(Tarjeta) if t.display]
            if visibles:
                visibles[0].focus()

    def on_resize(self) -> None:
        columnas = max(1, (self.query_one("#centro").size.width - 2) // 34)
        for g in self.query(Grid):
            g.styles.grid_size_columns = columnas

    def abrir_ficha(self, ficha: Ficha, consulta: str = "") -> None:
        if not ficha.campos:
            self.app.exit(("ejecutar", ficha.argv()))
            return
        self.app.push_screen(Formulario(ficha, self.p, consulta))

    def action_limpiar(self) -> None:
        mando = self.query_one("#mando", Input)
        if not mando.value:
            self.app.exit(None)
            return
        mando.value = ""
        tarjetas = [t for t in self.query(Tarjeta) if t.display]
        (tarjetas[0] if tarjetas else mando).focus()

    def action_hangar(self) -> None:
        self.app.switch_screen(Hangar())

    def action_restaurar(self) -> None:
        self.app.exit(("ejecutar", ["salir"]))

    def action_cerrar(self) -> None:
        self.app.exit(None)


def info_modo(id_modo: str | None) -> list[str]:
    """Datos vivos del modo para la columna INTEL (nunca falla)."""
    lineas: list[str] = []
    try:
        from ultron.nucleo import panel

        datos = panel.leer()
        pomo = datos.get("pomodoro") or {}
        if pomo.get("fin") and pomo["fin"] > time.time():
            resta = int(pomo["fin"] - time.time())
            lineas.append(f"Pomodoro: {resta // 60:02d}:{resta % 60:02d} ({pomo.get('fase', '')})")
        tareas = datos.get("tareas") or {}
        if tareas:
            lineas.append(f"Tareas de hoy: {tareas.get('hechas', 0)}/{tareas.get('total', 0)}")
        if datos.get("musica_sonando"):
            lineas.append("Música del modo sonando ♪")
    except Exception:  # noqa: BLE001
        pass
    try:
        from ultron.nucleo import xp

        ficha = xp.leer()
        lineas.append(f"Nivel {xp.nivel(ficha.get('xp', 0))} · {ficha.get('xp', 0)} XP · "
                      f"{len(ficha.get('logros', []))} logros")
    except Exception:  # noqa: BLE001
        pass
    if id_modo == "focus":
        try:
            from datetime import date

            from ultron.modos.focus.funciones import _eventos

            futuros = [e for _, e in _eventos() if e.fecha >= date.today()]
            if futuros:
                e = futuros[0]
                lineas.append(f"Próximo: {e.asignatura} en {(e.fecha - date.today()).days} días")
            else:
                lineas.append("Sin exámenes apuntados (ficha «Añadir examen»)")
        except Exception:  # noqa: BLE001
            pass
    if id_modo == "netanyahu":
        lineas.append(f"Nodo: {vista.ip_local()}")
        lineas.append("Uso ético: solo tu red o con permiso")
    if not lineas:
        lineas.append("Todo en orden.")
    return lineas


# ── ventanas emergentes ─────────────────────────────────────────────────────────


class Formulario(ModalScreen):
    """Pide los datos de una función con campos claros; Enter la lanza."""

    BINDINGS = [Binding("escape", "cancelar", "Cancelar")]

    def __init__(self, ficha: Ficha, p: dict[str, str], consulta: str = "") -> None:
        super().__init__()
        self.ficha, self.p = ficha, p
        self.sugerido = _sugerencia(ficha, consulta)

    def compose(self) -> ComposeResult:
        f = self.ficha
        with Vertical(id="caja"):
            cab = Text()
            cab.append(f" {f.icono} ", style=f"bold {self.p['fondo']} on {self.p['primario']}")
            cab.append(f"  {f.titulo}\n", style=f"bold {self.p['texto']}")
            cab.append(f.descripcion, style=self.p["apagado"])
            yield Static(cab, id="cab-form")
            for i, c in enumerate(f.campos):
                if c.tipo == "si_no":
                    yield Checkbox(c.etiqueta, id=f"c-{c.nombre}")
                    continue
                yield Static(c.etiqueta + ("" if c.obligatorio else "  (opcional)"),
                             classes="etiqueta")
                valor = self.sugerido if i == 0 and self.sugerido else c.defecto
                with Horizontal(classes="fila"):
                    yield Input(value=valor, id=f"c-{c.nombre}",
                                type="integer" if c.tipo == "numero" else "text")
                    if c.tipo in ("archivo", "carpeta"):
                        yield Button("📂", id=f"x-{c.nombre}", classes="explorar")
            yield Static(id="error-form")
            with Horizontal(classes="fila"):
                yield Button("▶  EJECUTAR", id="ejecutar", variant="primary")
                yield Button("Cancelar", id="cancelar")

    def on_mount(self) -> None:
        caja = self.query_one("#caja")
        caja.styles.border = ("heavy", self.p["primario"])
        caja.styles.background = self.p["fondo"]
        entradas = list(self.query(Input))
        if entradas:
            entradas[0].focus()

    def valores(self) -> dict[str, str]:
        datos: dict[str, str] = {}
        for c in self.ficha.campos:
            w = self.query_one(f"#c-{c.nombre}")
            datos[c.nombre] = ("1" if w.value else "") if isinstance(w, Checkbox) \
                else str(w.value)
        return datos

    def action_ejecutar(self) -> None:
        valores = self.valores()
        faltan = self.ficha.faltan(valores)
        if faltan:
            self.query_one("#error-form", Static).update(
                Text(f"Falta: {faltan[0].etiqueta}", style=self.p["error"]))
            self.query_one(f"#c-{faltan[0].nombre}").focus()
            return
        for c in self.ficha.campos:
            if c.tipo in ("archivo", "carpeta") and valores.get(c.nombre):
                valores[c.nombre] = _expandir(valores[c.nombre])
        self.app.exit(("ejecutar", self.ficha.argv(valores)))

    def action_cancelar(self) -> None:
        self.dismiss(None)

    def on_input_submitted(self) -> None:
        self.action_ejecutar()

    def on_button_pressed(self, evento: Button.Pressed) -> None:
        bid = evento.button.id or ""
        if bid.startswith("x-"):
            nombre = bid[2:]
            campo = next(c for c in self.ficha.campos if c.nombre == nombre)

            def poner(ruta: str | None) -> None:
                if ruta:
                    self.query_one(f"#c-{nombre}", Input).value = ruta

            self.app.push_screen(Explorador(campo.tipo == "carpeta", self.p), poner)
            return
        getattr(self, f"action_{bid}")()


def _expandir(ruta: str) -> str:
    from pathlib import Path

    return str(Path(ruta).expanduser())


def _sugerencia(ficha: Ficha, consulta: str) -> str:
    """De «investiga ubuntu.com» saca «ubuntu.com» para el primer campo."""
    if not consulta or not ficha.campos or ficha.campos[0].tipo == "si_no":
        return ""
    palabras = consulta.split()
    normales = {catalogo._normal(w) for w in (ficha.titulo + " " + ficha.claves).split()}
    resto = [w for w in palabras if catalogo._normal(w)[:5] not in
             {n[:5] for n in normales} and len(w) > 2]
    if ficha.campos[0].tipo in ("archivo", "carpeta"):
        return next((w for w in resto if "." in w or "/" in w), "")
    return " ".join(resto) if len(resto) <= 4 else ""


class Explorador(ModalScreen):
    """Elegir un archivo o carpeta con el ratón o las flechas."""

    BINDINGS = [Binding("escape", "cancelar", "Cancelar")]

    def __init__(self, carpeta: bool, p: dict[str, str]) -> None:
        super().__init__()
        self.carpeta, self.p = carpeta, p

    def compose(self) -> ComposeResult:
        from pathlib import Path

        with Vertical(id="caja"):
            yield Static(Text("Elige una carpeta y pulsa «Usar esta carpeta»" if self.carpeta
                              else "Elige un archivo (Enter o doble clic)",
                              style=f"bold {self.p['primario']}"))
            yield DirectoryTree(str(Path.home()), id="arbol")
            if self.carpeta:
                yield Button("✔  Usar esta carpeta", id="usar", variant="primary")

    def on_mount(self) -> None:
        caja = self.query_one("#caja")
        caja.styles.border = ("heavy", self.p["primario"])
        caja.styles.background = self.p["fondo"]
        caja.styles.height = "85%"
        self.query_one("#arbol").focus()

    def on_directory_tree_file_selected(self, evento: DirectoryTree.FileSelected) -> None:
        if not self.carpeta:
            self.dismiss(str(evento.path))

    def on_button_pressed(self) -> None:
        nodo = self.query_one("#arbol", DirectoryTree).cursor_node
        if nodo and nodo.data:
            ruta = nodo.data.path
            self.dismiss(str(ruta if ruta.is_dir() else ruta.parent))

    def action_cancelar(self) -> None:
        self.dismiss(None)


class PedirIA(ModalScreen):
    """Cuando lo escrito no es ninguna función: preguntar, ejecutar o buscar."""

    BINDINGS = [Binding("escape", "cancelar", "Cancelar")]

    def __init__(self, texto: str, p: dict[str, str]) -> None:
        super().__init__()
        self.texto, self.p = texto, p

    def compose(self) -> ComposeResult:
        with Vertical(id="caja"):
            yield Static(Text(f"«{self.texto}»\n¿Qué hago con esto?",
                              style=f"bold {self.p['primario']}"))
            yield OptionList(
                Option(Text("✦  Preguntárselo a ULTRON (IA)"), id="preguntar"),
                Option(Text("⚙  Hacerlo en mi equipo (propone comandos, tú apruebas)"), id="haz"),
                Option(Text("⌕  Buscar archivos que hablen de esto"), id="buscar"),
                id="opciones")

    def on_mount(self) -> None:
        caja = self.query_one("#caja")
        caja.styles.border = ("heavy", self.p["primario"])
        caja.styles.background = self.p["fondo"]
        self.query_one("#opciones").focus()

    def on_option_list_option_selected(self, evento: OptionList.OptionSelected) -> None:
        argv = {"preguntar": ["ia", "preguntar", self.texto], "haz": ["haz", self.texto],
                "buscar": ["buscar", self.texto]}[evento.option.id or "preguntar"]
        self.app.exit(("ejecutar", argv))

    def action_cancelar(self) -> None:
        self.dismiss(None)


# ── la aplicación ───────────────────────────────────────────────────────────────

CSS = """
Screen { layout: vertical; }
#cabecera { height: 1; margin: 1 1 0 1; }
#pie { dock: bottom; height: 1; margin: 0 1; }
#cuerpo { height: 1fr; margin: 0 1; }
.titulo { height: 1; margin: 1 0 0 0; text-style: bold; }
#reactor { width: 100%; height: auto; content-align: center middle; margin-top: 2; }
#log { width: 100%; height: auto; content-align: center top; margin-top: 1; }
#col-modos { width: 30; }
#modos { height: 1fr; background: transparent; border: none; }
#col-holo { width: 1fr; margin: 0 1; }
#holo { height: 1fr; min-height: 8; }
#nombre { height: auto; content-align: center middle; margin-top: 1; }
#col-info { width: 44; padding: 1 1; }
#botones { height: 3; margin: 0 1; align: center middle; }
#botones Button { margin: 0 1; min-width: 20; }
#mando { margin: 1 1 0 1; }
#telemetria { width: 32; padding: 1 1; }
#centro { width: 1fr; margin: 0 1; padding: 0 1; }
#intel { width: 38; padding: 1 1; }
#aviso { margin: 1 0 0 0; padding: 0 1; }
.rejilla { grid-size: 3; grid-gutter: 0 1; height: auto; grid-rows: 5; }
.tarjeta { height: 5; padding: 0 1; }
Formulario, Explorador, PedirIA { align: center middle; background: rgba(0,0,0,0.6); }
#caja { width: 76; height: auto; max-height: 90%; padding: 1 2; }
.etiqueta { margin-top: 1; }
.fila { height: auto; }
.fila Input { width: 1fr; }
.explorar { min-width: 6; width: 6; }
#error-form { height: 1; margin-top: 1; }
#opciones { height: auto; margin-top: 1; }
#arbol { height: 1fr; }
"""


class Nexus(App):
    CSS = CSS
    TITLE = "ULTRON NEXUS"

    def __init__(self, arranque: bool = True, pantalla: str | None = None,
                 aviso: str = "", funcion: str | None = None) -> None:
        super().__init__()
        self.arranque, self.pantalla, self.aviso, self.funcion = (arranque, pantalla, aviso,
                                                                  funcion)

    def on_mount(self) -> None:
        activo = estado.modo_activo()
        if self.pantalla == "hangar" or (not activo and self.pantalla != "puente"):
            destino: Screen = Hangar()
        else:
            destino = Puente(activo, self.aviso)
        if self.arranque:
            self.push_screen(Arranque(destino, paleta(activo)))
        else:
            self.push_screen(destino)
        if self.funcion:
            ficha = catalogo.buscar_comando(self.funcion)
            if ficha is not None and ficha.campos:
                self.push_screen(Formulario(ficha, paleta(activo)))
