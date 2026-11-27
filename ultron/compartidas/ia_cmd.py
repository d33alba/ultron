"""Comandos `ultron ia …`: configurar, modelo, estado, probar, chat y preguntas sueltas."""

from __future__ import annotations

import os
import stat
import sys

import typer
from typer.core import TyperGroup

from ultron.ia import errores as E
from ultron.ia.ajustes import PROVEEDORES, AjustesIA, detectar_locales, guardar, resolver
from ultron.ia.base import es_url_local as _es_local
from ultron.ia.cliente import crear, obtener_cliente, preguntar_stream
from ultron.ia.personalidad import temperatura
from ultron.ui import tema


class _GrupoIA(TyperGroup):
    """Permite `ultron ia "pregunta"` además de los subcomandos."""

    def parse_args(self, ctx, args):  # type: ignore[override]
        if args and args[0] not in self.commands and not args[0].startswith("-"):
            args = ["preguntar", *args]
        return super().parse_args(ctx, args)


grupo = typer.Typer(
    cls=_GrupoIA,
    help="IA del modo activo: configurar, cambiar de modelo, chatear o preguntar.",
    no_args_is_help=True,
)
app = typer.Typer()
app.add_typer(grupo, name="ia")

_OPCIONES: dict[str, str | None] = {"modelo": None}


@grupo.callback()
def _cb(
    modelo: str = typer.Option(None, "--modelo", "-m", help="Usa este modelo solo esta vez."),
) -> None:
    _OPCIONES["modelo"] = modelo


def _t() -> tema.Tema:
    return tema.actual()


def _imprimir_stream(trozos) -> str:
    c = _t().consola
    texto = []
    for trozo in trozos:
        texto.append(trozo)
        c.print(trozo, end="", markup=False, highlight=False, soft_wrap=True)
    c.print()
    return "".join(texto)


def _stdin_canalizado() -> str:
    """Texto recibido por tubería o archivo (`cat x | ultron ia "resume"`); vacío si no hay."""
    try:
        modo = os.fstat(sys.stdin.fileno()).st_mode
    except (OSError, ValueError, AttributeError):
        return ""
    if not (stat.S_ISFIFO(modo) or stat.S_ISREG(modo)):
        return ""
    try:
        return sys.stdin.read().strip()
    except OSError:
        return ""


@grupo.command("preguntar", hidden=True)
def cmd_preguntar(texto: list[str] = typer.Argument(..., help="La pregunta.")) -> None:
    """Una pregunta suelta a la IA del modo activo (respuesta en streaming)."""
    pregunta = " ".join(texto)
    entrada = _stdin_canalizado()
    if entrada:
        pregunta = f"{pregunta}\n\n{entrada}"
    _imprimir_stream(preguntar_stream(pregunta, modelo=_OPCIONES["modelo"],
                                      temperatura=temperatura()))


@grupo.command("chat")
def cmd_chat() -> None:
    """Chat interactivo con la personalidad del modo activo."""
    t = _t()
    c = t.consola
    modelo = _OPCIONES["modelo"]
    cliente = obtener_cliente(modelo)
    c.print(t.panel(
        f"[acento]{cliente.modelo}[/] [apagado]· {cliente.aj.url_base}[/]\n"
        "[apagado]/salir · /limpiar · /modelo <nombre>[/]",
        titulo="Chat con ULTRON",
    ))
    historial: list[dict] = []
    while True:
        try:
            entrada = c.input(f"[primario]{t.glifo('flecha') or '>'}[/] ").strip()
        except (EOFError, KeyboardInterrupt):
            c.print()
            return
        if not entrada:
            continue
        if entrada in ("/salir", "/exit", "/q"):
            return
        if entrada == "/limpiar":
            historial.clear()
            t.ok("Conversación borrada.")
            continue
        if entrada.startswith("/modelo"):
            partes = entrada.split(maxsplit=1)
            if len(partes) == 2:
                modelo = partes[1]
                t.ok(f"Modelo: {modelo}")
            continue
        c.print(f"[acento]{t.glifo('marca')}[/] ", end="")
        try:
            respuesta = _imprimir_stream(preguntar_stream(
                entrada, modelo=modelo, historial=historial, temperatura=temperatura()))
        except E.IAError as e:
            t.error(e.mensaje)
            if e.sugerencia:
                t.info(e.sugerencia)
            continue
        historial += [{"role": "user", "content": entrada},
                      {"role": "assistant", "content": respuesta}]
        historial = historial[-12:]  # contexto corto para modelos locales


@grupo.command("estado")
def cmd_estado() -> None:
    """Proveedor, URL, modelo y clave (enmascarada), y de dónde sale cada valor."""
    t = _t()
    aj = resolver()
    if aj is None:
        t.aviso("No hay IA configurada. Ejecuta: [acento]ultron ia configurar[/]")
        raise typer.Exit(2)
    tabla = t.tabla("Campo", "Valor", "Origen", titulo="IA de Ultron")
    for campo, valor, origen in (
        ("Proveedor", PROVEEDORES.get(aj.proveedor, {}).get("nombre", aj.proveedor), "proveedor"),
        ("URL", aj.url_base, "url_base"),
        ("Modelo", aj.modelo or "—", "modelo"),
        ("Clave", aj.clave_enmascarada(), "clave"),
    ):
        tabla.add_row(campo, valor, aj.origen.get(origen, "—"))
    tabla.add_row("Timeout", f"{aj.timeout:.0f} s", "config")
    t.consola.print(tabla)


@grupo.command("probar")
def cmd_probar() -> None:
    """Hace una llamada real y diagnostica cualquier problema."""
    t = _t()
    aj = resolver(modelo=_OPCIONES["modelo"])
    if aj is None:
        raise E.IANoConfigurada()
    cliente = crear(aj)
    with t.spinner_ctx(f"Probando {aj.url_base}"):
        try:
            disponibles = cliente.modelos()
        except E.IAError as e:
            t.error(e.mensaje)
            if e.sugerencia:
                t.info(e.sugerencia)
            raise typer.Exit(1) from None
        if not cliente.modelo and disponibles:
            cliente.modelo = disponibles[0]
        diag = cliente.probar()
    t.info(f"Modelos en el servidor: {len(disponibles)}")
    if diag.ok:
        t.ok(diag.mensaje)
        if diag.ejemplo:
            t.consola.print(f"[apagado]Respuesta: {diag.ejemplo}[/]")
        return
    t.error(diag.mensaje)
    if diag.error and diag.error.sugerencia:
        t.info(diag.error.sugerencia)
    raise typer.Exit(1)


@grupo.command("modelo")
def cmd_modelo(nombre: str = typer.Argument(None, help="Modelo nuevo (vacío: lista).")) -> None:
    """Lista los modelos del servidor o cambia el modelo por defecto."""
    t = _t()
    aj = resolver()
    if aj is None:
        raise E.IANoConfigurada()
    if nombre:
        aj.modelo = nombre
        guardar(aj)
        t.ok(f"Modelo por defecto: [acento]{nombre}[/]")
        return
    disponibles = crear(aj).modelos()
    tabla = t.tabla("", "Modelo", titulo=f"Modelos en {aj.url_base}")
    for m in disponibles:
        tabla.add_row(t.glifo("ok") if m == aj.modelo else "", m)
    t.consola.print(tabla)


@grupo.command("configurar")
def cmd_configurar(
    url: str = typer.Option(None, "--url", help="URL base (p. ej. http://localhost:11434/v1)."),
    modelo: str = typer.Option(None, "--modelo", help="Modelo."),
    clave: str = typer.Option(None, "--clave", help="Clave de API (opcional en local)."),
    proveedor: str = typer.Option(None, "--proveedor", help="local, openai, anthropic…"),
    sin_probar: bool = typer.Option(False, "--sin-probar", help="Guarda sin hacer la prueba."),
    sin_verificar_tls: bool = typer.Option(
        False, "--sin-verificar-tls",
        help="Acepta el certificado propio de un servidor interno (p. ej. el del instituto)."),
) -> None:
    """Asistente para conectar la IA (o sin preguntas con --url/--modelo)."""
    t = _t()
    c = t.consola
    if url or proveedor:
        prov = proveedor or "local"
        if clave is None and not _es_local(url or "") and sys.stdin.isatty():
            clave = typer.prompt("Clave de API (Enter si no hace falta)", default="",
                                 hide_input=True, show_default=False) or None
        aj = AjustesIA(
            proveedor=prov,
            url_base=url or PROVEEDORES.get(prov, PROVEEDORES["local"])["url"],
            modelo=modelo or "",
            clave=clave,
        )
    else:
        aj = _asistente(t)
    if sin_verificar_tls:
        aj.verificar_tls = False
    if not sin_probar:
        cliente = crear(aj)
        with t.spinner_ctx("Probando la conexión"):
            if not aj.modelo:
                try:
                    disponibles = cliente.modelos()
                except E.IAError:
                    disponibles = []
                if disponibles:
                    aj.modelo = cliente.modelo = disponibles[0]
            diag = cliente.probar()
        if not diag.ok and aj.verificar_tls is True and "certificado" in diag.mensaje:
            t.aviso(diag.mensaje)
            if typer.confirm("¿Confío en el certificado de este servidor y vuelvo a probar?",
                             default=True):
                aj.verificar_tls = False
                cliente = crear(aj)
                with t.spinner_ctx("Probando otra vez"):
                    diag = cliente.probar()
        if not diag.ok:
            t.error(diag.mensaje)
            if diag.error and diag.error.sugerencia:
                t.info(diag.error.sugerencia)
            if not typer.confirm("¿Guardar igualmente?", default=False):
                raise typer.Exit(1)
        else:
            t.ok(diag.mensaje)
    guardar(aj)
    t.ok("Configuración guardada en ~/.config/ultron/config.toml (permisos 600).")
    c.print("[apagado]Prueba:[/] [acento]ultron ia \"hola\"[/]")


def _asistente(t: tema.Tema) -> AjustesIA:
    c = t.consola
    c.print(t.panel("Voy a buscar servidores de IA en este equipo…", titulo="Configurar IA"))
    with t.spinner_ctx("Buscando Ollama y LM Studio"):
        locales = detectar_locales(timeout=1.0)
    if locales:
        for i, (prov, url, modelos) in enumerate(locales, 1):
            c.print(f"  [acento]{i}[/] {PROVEEDORES[prov]['nombre']} en {url} "
                    f"[apagado]({len(modelos)} modelos)[/]")
        c.print(f"  [acento]{len(locales) + 1}[/] Otro servidor o proveedor")
        eleccion = typer.prompt("Elige", default=1, type=int)
        if 1 <= eleccion <= len(locales):
            prov, url, modelos = locales[eleccion - 1]
            return AjustesIA(proveedor=prov, url_base=url, modelo=_elegir_modelo(t, modelos))
    claves = list(PROVEEDORES)
    for i, prov in enumerate(claves, 1):
        c.print(f"  [acento]{i}[/] {PROVEEDORES[prov]['nombre']}")
    idx = typer.prompt("Proveedor", default=1, type=int)
    prov = claves[max(1, min(idx, len(claves))) - 1]
    url = typer.prompt("URL base", default=PROVEEDORES[prov]["url"])
    clave = typer.prompt("Clave de API (Enter si no hace falta)", default="",
                         hide_input=True, show_default=False) or None
    aj = AjustesIA(proveedor=prov, url_base=url, clave=clave)
    try:
        modelos = crear(aj).modelos()
    except E.IAError as e:
        t.aviso(f"No puedo listar modelos: {e.mensaje}")
        modelos = []
    aj.modelo = _elegir_modelo(t, modelos)
    return aj


def _elegir_modelo(t: tema.Tema, modelos: list[str]) -> str:
    if not modelos:
        return typer.prompt("Nombre del modelo")
    for i, m in enumerate(modelos, 1):
        t.consola.print(f"  [acento]{i}[/] {m}")
    eleccion = typer.prompt("Modelo (número o nombre)", default="1")
    if eleccion.isdigit() and 1 <= int(eleccion) <= len(modelos):
        return modelos[int(eleccion) - 1]
    return eleccion
