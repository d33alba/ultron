"""CLI raíz de Ultron."""

from __future__ import annotations

import importlib
import pkgutil
import sys
from typing import Any

import typer
from rich.text import Text
from typer.core import TyperGroup

from ultron import __version__
from ultron.nucleo import entrega, estado, motor, registro, xp
from ultron.nucleo.doctor import OpcionesDoctor
from ultron.nucleo.doctor import ejecutar as ejecutar_doctor
from ultron.nucleo.ejecutor import Ejecutor, ErrorEjecucion
from ultron.nucleo.esquema import ErrorEsquema
from ultron.ui import animaciones, banner, tema
from ultron.ui import espanol as _espanol


class GrupoUltron(TyperGroup):
    def parse_args(self, ctx, args):
        antes_del_separador = args[:args.index("--")] if "--" in args else args
        ctx.meta["ultron_simulado"] = "--simular" in antes_del_separador
        return super().parse_args(ctx, args)

    def invoke(self, ctx):
        previo = estado.modo_activo()
        resultado = super().invoke(ctx)
        if ctx.invoked_subcommand and not ctx.meta["ultron_simulado"]:
            try:
                xp.registrar(ctx.invoked_subcommand, modo_previo=previo)
            except (OSError, ErrorEjecucion):
                tema.actual().aviso("No se pudo guardar o anunciar la experiencia.")
        return resultado


_espanol.aplicar()

app = typer.Typer(
    cls=GrupoUltron,
    name="ultron",
    help="Transforma Ubuntu entero según el modo: estética, terminal, sonidos, IA y funciones.",
    no_args_is_help=False,
    add_completion=True,
    rich_markup_mode="rich",
    context_settings={"help_option_names": ["-h", "--help"]},
)

GLOBAL: dict[str, Any] = {"simular": False}


def _version(valor: bool) -> None:
    if valor:
        tema.actual().consola.print(f"Ultron {__version__}")
        raise typer.Exit()


@app.callback(invoke_without_command=True)
def raiz(
    ctx: typer.Context,
    simular: bool = typer.Option(False, "--simular", help="Enseña los cambios sin hacerlos."),
    sin_animaciones: bool = typer.Option(False, "--sin-animaciones", help="Sin animaciones."),
    sin_color: bool = typer.Option(False, "--sin-color", help="Sin colores."),
    version: bool = typer.Option(
        False, "--version", "-V", callback=_version, is_eager=True, help="Versión de Ultron."
    ),
) -> None:
    """Ultron: elige un modo y tu sistema se convierte en otro."""
    GLOBAL["simular"] = simular
    tema.configurar(sin_animaciones=sin_animaciones, sin_color=sin_color)
    if ctx.invoked_subcommand is None:
        if sys.stdin.isatty() and sys.stdout.isatty():
            try:
                from ultron.ui.nexus import abrir
            except ImportError:
                pass
            else:
                abrir()
                return
        tema.actual().consola.print(ctx.get_help())


# --- nexus -------------------------------------------------------------------


@app.command("nexus")
def cmd_nexus(
    funcion: str = typer.Option(None, "--funcion", "-f", help="Abre directamente una función."),
    modos: bool = typer.Option(False, "--modos", help="Empieza en la elección de modo."),
) -> None:
    """Centro de mando a pantalla completa: todo con flechas, Enter o el ratón."""
    from ultron.ui.nexus import abrir

    abrir(pantalla="hangar" if modos else None, funcion=funcion)


@app.command("lanzar", hidden=True)
def cmd_lanzar(
    funcion: str = typer.Argument(..., help="Función del catálogo (p. ej. osint-dominio)."),
    archivos: list[str] = typer.Argument(None, help="Archivos soltados sobre el lanzador."),
) -> None:
    """Lo usan los iconos del escritorio, el dock y Archivos: abre la función sin comandos."""
    from ultron.ui import nexus
    from ultron.ui.nexus import catalogo

    ficha = catalogo.buscar_comando(funcion)
    if ficha is None:
        tema.actual().error(f"No conozco la función «{funcion}».")
        raise typer.Exit(1)
    archivos = [a for a in (archivos or []) if a]
    if ficha.soltar and archivos:
        codigo = 0
        for archivo in archivos:
            codigo = nexus.ejecutar_ultron(ficha.argv({ficha.soltar: archivo})) or codigo
        nexus.pausa_final(codigo)
    elif not ficha.campos:
        codigo = nexus.ejecutar_ultron(ficha.argv())
        if codigo or not ficha.ventana:
            nexus.pausa_final(codigo)
    else:
        nexus.abrir(funcion=ficha.comando)


# --- modos -------------------------------------------------------------------


grupo_modos = typer.Typer(help="Lista, consulta y crea modos.")
app.add_typer(grupo_modos, name="modos")


@grupo_modos.callback(invoke_without_command=True)
def cmd_modos(
    ctx: typer.Context,
    detalle: str = typer.Option(None, "--detalle", "-d", help="Enseña un modo en detalle."),
) -> None:
    """Lista los modos disponibles, cada uno con su propio estilo."""
    if ctx.invoked_subcommand is not None:
        return
    t = tema.actual()
    c = t.consola
    if detalle:
        _detalle_modo(detalle)
        return
    activo = estado.modo_activo()
    tabla = t.tabla("", "Modo", "Lema", "Funciones", titulo="Modos de Ultron")
    for modo in registro.listar():
        tm = tema.cargar_tema(modo.id)
        color = tm.paleta.get("primario", "")
        acento = tm.paleta.get("acento", "")
        nombre = Text(modo.nombre, style=f"bold {color}")
        if modo.id == activo:
            nombre.append("  ● ACTIVO", style=f"bold {acento}")
        funciones = ", ".join(modo.funciones[:6]) + ("…" if len(modo.funciones) > 6 else "")
        tabla.add_row(
            Text(tm.glifo("marca"), style=color),
            nombre,
            Text(modo.lema, style=acento),
            Text(funciones or "—", style="apagado"),
        )
    c.print(tabla)
    c.print("[apagado]Entra en uno con:[/] [acento]ultron entrar <modo>[/]  "
            "[apagado]· detalle:[/] [acento]ultron modos -d <modo>[/]")


@grupo_modos.command("nuevo")
def cmd_modo_nuevo(id_modo: str) -> None:
    """Genera la plantilla de un modo personal."""
    entrega.crear_modo(id_modo, simular=GLOBAL["simular"])


@app.command("demo")
def cmd_demo(
    ctx: typer.Context,
    rapida: bool = typer.Option(False, "--rapida", help="Un ejemplo por modo, sin pausas."),
) -> None:
    """Recorre los cinco modos con ejemplos que funcionan sin red ni IA."""
    raiz = ctx.find_root()

    def ejecutar(args: tuple[str, ...]) -> None:
        comando = raiz.command.get_command(raiz, args[0])
        with comando.make_context(args[0], list(args[1:]), parent=raiz) as contexto:
            comando.invoke(contexto)

    entrega.recorrer(ejecutar, rapida=rapida, simular=GLOBAL["simular"])


def _detalle_modo(id_modo: str) -> None:
    modo = registro.obtener(id_modo)
    tm = tema.cargar_tema(modo.id)
    banner.mostrar_banner(tm, animado=False)
    c = tm.consola
    c.print(f"\n[bold primario]{modo.nombre}[/] [apagado]·[/] [acento]{modo.lema}[/]")
    c.print(f"[texto]{modo.descripcion}[/]\n")
    tabla = tm.tabla("Capa", "Qué cambia")
    clases, desconocidas = motor.capas_del_modo(modo)
    for cls in clases:
        tabla.add_row(cls.nombre, cls.descripcion or "—")
    for nombre in desconocidas:
        tabla.add_row(nombre, "[apagado](llega en una versión posterior)[/]")
    c.print(tabla)
    if modo.funciones:
        c.print("[bold acento]Funciones:[/] " + ", ".join(modo.funciones))


# --- entrar / salir / estado --------------------------------------------------

_ICONOS = {"aplicada": "ok", "restaurada": "ok", "saltada": "aviso", "fallida": "error"}


def _imprimir_progreso(t: tema.Tema):
    def progreso(capa: str, est: str) -> None:
        if est not in _ICONOS:
            return
        estilo = {"ok": "ok", "aviso": "aviso", "error": "error"}[_ICONOS[est]]
        g = t.glifo(_ICONOS[est])
        t.consola.print(f"  [acento]{t.glifo('info')}[/] {capa:<12} [{estilo}]{g} {est}[/]")

    return progreso


def _lista(valor: str | None) -> list[str] | None:
    return [v.strip() for v in valor.split(",")] if valor else None


@app.command("entrar")
def cmd_entrar(
    id_modo: str = typer.Argument(..., help="Modo: netanyahu, focus, gaming, presentacion…"),
    simular: bool = typer.Option(False, "--simular", help="Enseña los cambios sin hacerlos."),
    solo: str = typer.Option(None, "--solo", help="Solo estas capas (separadas por comas)."),
    excepto: str = typer.Option(None, "--excepto", help="Todas menos estas capas."),
    sin_sudo: bool = typer.Option(False, "--sin-sudo", help="Salta las capas que piden sudo."),
    si: bool = typer.Option(False, "--si", "-y", help="No preguntes: acepta todo."),
    arranque: bool = typer.Option(
        False, "--arranque", help="Cambia también el arranque: Plymouth, GRUB y GDM (sudo)."
    ),
    sin_carga: bool = typer.Option(False, "--sin-carga", help="Sin pantalla de carga."),
    como_ubuntu: bool = typer.Option(
        False, "--como-ubuntu", help="Al simular, supón que hay GNOME y todas las herramientas."
    ),
) -> None:
    """Transforma el sistema con un modo."""
    import os

    from ultron.ui import carga

    simular = simular or GLOBAL["simular"]
    if arranque:
        os.environ["ULTRON_ARRANQUE"] = "1"
    modo = registro.obtener(id_modo)
    viejo_id = estado.modo_activo()
    viejo = tema.cargar_tema(viejo_id) if viejo_id else None
    nuevo = tema.cargar_tema(modo.id)
    animaciones.transicion(viejo, nuevo)
    c = nuevo.consola
    if simular:
        c.print(f"[aviso]Simulación del modo {modo.nombre}: no se cambia nada.[/]")
    else:
        c.print(f"[bold primario]{nuevo.glifo('marca')} Entrando en {modo.nombre}…[/]")

    import platform

    ej = Ejecutor(simular=simular, consola=c,
                  suponer=como_ubuntu or platform.system() != "Linux")
    clases, _ = motor.capas_del_modo(modo, _lista(solo), _lista(excepto))
    from ultron.capas.base import Contexto

    ctx = Contexto(modo=modo, dir_modo=modo.dir, consola=c)
    con_sudo = [cl.nombre for cl in clases if cl.requiere_sudo and cl(ej, ctx).disponible()[0]]
    if "bloquear" in (modo.capas.get("sistema") or {}):
        con_sudo.append("sistema (bloqueo de webs)")
    acepta_sudo = not sin_sudo
    if con_sudo and not simular and not sin_sudo:
        # se pregunta ANTES de la pantalla de carga, que tapa la terminal
        acepta_sudo = si or typer.confirm(
            f"{', '.join(con_sudo)} necesita permisos de administrador (sudo). ¿Seguir?",
            default=True,
        )
        if acepta_sudo and ej.existe("sudo"):
            ej.run(["sudo", "-v"], check=False, timeout=None)

    nombres = [cl.nombre for cl in clases]

    def trabajo(progreso):
        return motor.entrar(
            modo.id, ej=ej, solo=_lista(solo), excepto=_lista(excepto),
            sin_sudo=not acepta_sudo, confirmar_sudo=lambda _capas: acepta_sudo,
            progreso=progreso, consola=c,
        )

    if simular:
        motor.entrar(modo.id, ej=ej, solo=_lista(solo), excepto=_lista(excepto),
                     progreso=_imprimir_progreso(nuevo), consola=c)
    else:
        carga.ejecutar(nuevo, f"{nuevo.glifo('marca')} {modo.nombre}", nombres, trabajo,
                       usar_gtk=not sin_carga)
    if simular:
        c.print(f"[apagado]{len(ej.historial)} operaciones simuladas.[/]")
        return
    tema.invalidar()
    final = tema.cargar_tema(modo.id)
    final.consola.print()
    banner.mostrar_banner(final)
    final.consola.print(f"\n[acento]{final.frase('ok', 'Modo activado.')}[/]")
    final.consola.print("[apagado]Abre una terminal nueva para ver el prompt del modo. "
                        "Para deshacerlo todo: ultron salir[/]")
    from ultron.nucleo import voz

    voz.anunciar_modo(modo.id)


@app.command("salir")
def cmd_salir(
    simular: bool = typer.Option(False, "--simular", help="Enseña los cambios sin hacerlos."),
) -> None:
    """Sale del modo activo y deja el sistema exactamente como estaba."""
    simular = simular or GLOBAL["simular"]
    t = tema.actual()
    c = t.consola
    if not motor.leer_instantanea():
        t.info("No hay ningún modo activo.")
        return
    ej = Ejecutor(simular=simular, consola=c)
    resultados = motor.salir(ej=ej, progreso=_imprimir_progreso(t), consola=c)
    fallidas = [r for r in resultados if r.estado == "fallida"]
    t2 = tema.actual()
    if fallidas:
        for r in fallidas:
            t2.error(f"{r.nombre}: {r.motivo}")
        raise typer.Exit(1)
    t2.ok("Sistema restaurado." if not simular else "Simulación de salida completa.")
    if not simular:
        from ultron.nucleo import voz

        voz.anunciar_modo(None)


@app.command("estado")
def cmd_estado() -> None:
    """Muestra el modo activo y qué capas ha cambiado."""
    t = tema.actual()
    datos = estado.leer()
    activo = datos.get("modo_activo")
    if not activo:
        t.info("Sin modo activo. Prueba: [acento]ultron modos[/]")
        if motor.leer_instantanea():
            t.aviso("Hay una instantánea pendiente: ejecuta [acento]ultron salir[/] "
                    "para restaurar.")
        return
    tabla = t.tabla("Capa", "Estado", "Detalle")
    for capa in datos.get("capas", []):
        tabla.add_row(capa.get("nombre", ""), capa.get("estado", ""), capa.get("motivo", ""))
    modo = registro.obtener(activo)
    t.consola.print(t.panel(
        f"[bold primario]{modo.nombre}[/] [apagado]desde {datos.get('desde', '?')}[/]",
        titulo="Modo activo",
    ))
    t.consola.print(tabla)


# --- doctor / bienvenida / prompt --------------------------------------------


@app.command("doctor")
def cmd_doctor(
    sin_ia: bool = typer.Option(False, "--sin-ia", help="No pruebes la conexión con la IA."),
    completo: bool = typer.Option(False, "--completo", help="Revisa también las dependencias."),
) -> None:
    """Diagnostica el sistema, las dependencias, los recursos y la IA."""
    t = tema.actual()
    with t.spinner_ctx("Revisando el sistema"):
        resultados = ejecutar_doctor(Ejecutor(), OpcionesDoctor(sin_ia=sin_ia, completo=completo))
    tabla = t.tabla("", "Comprobación", "Resultado", "Solución", titulo="Ultron doctor")
    estilos = {"ok": ("ok", "ok"), "aviso": ("aviso", "aviso"), "error": ("error", "error")}
    for r in resultados:
        glifo, estilo = estilos.get(r.estado, ("info", "texto"))
        tabla.add_row(f"[{estilo}]{t.glifo(glifo)}[/]", r.nombre, r.detalle, r.solucion)
    t.consola.print(tabla)
    if completo:
        pendientes = [r for r in resultados if r.estado != "ok"]
        if pendientes:
            t.aviso("Pendiente para la corrección")
            for r in pendientes:
                t.consola.print(Text(f"• {r.nombre} · {r.detalle} · {r.solucion}"))
        else:
            t.ok("Listo para corregir ✔")
        if any(r.estado == "error" for r in pendientes):
            raise typer.Exit(1)
        if pendientes:
            raise typer.Exit(2)
        return
    errores = sum(r.estado == "error" for r in resultados)
    avisos = sum(r.estado == "aviso" for r in resultados)
    if errores:
        t.error(f"{errores} errores y {avisos} avisos.")
        raise typer.Exit(1)
    t.ok("Listo ✔" if not avisos else f"Funciona, con {avisos} avisos.")


@app.command("bienvenida", hidden=True)
def cmd_bienvenida() -> None:
    t = tema.actual()
    banner.mostrar_banner(t, animado=False, compacto=True)
    frase = t.frase("bienvenida")
    if frase:
        t.consola.print(f"[apagado]{frase}[/]")


@app.command("prompt-extra", hidden=True)
def cmd_prompt_extra() -> None:
    from ultron.prompt_extra import texto

    sys.stdout.write(texto())


# --- registro de módulos -----------------------------------------------------


def _fusionar(sub: typer.Typer) -> None:
    existentes = {c.name for c in app.registered_commands if c.name}
    for comando in sub.registered_commands:
        nombre = comando.name or (comando.callback.__name__ if comando.callback else None)
        if nombre in existentes:
            continue
        app.registered_commands.append(comando)
    app.registered_groups.extend(sub.registered_groups)


def _registrar_modulos() -> None:
    try:
        import ultron.compartidas as compartidas
    except ImportError:
        compartidas = None
    if compartidas is not None:
        for info in pkgutil.iter_modules(compartidas.__path__):
            modulo = importlib.import_module(f"ultron.compartidas.{info.name}")
            if isinstance(getattr(modulo, "app", None), typer.Typer):
                _fusionar(modulo.app)
    for modo in registro.listar():
        try:
            modulo = importlib.import_module(f"ultron.modos.{modo.id}.funciones")
        except ImportError:
            continue
        if isinstance(getattr(modulo, "app", None), typer.Typer):
            _fusionar(modulo.app)


_registrar_modulos()


def _errores_conocidos() -> tuple[type[BaseException], ...]:
    tipos: list[type[BaseException]] = [
        motor.ErrorMotor, registro.ModoNoEncontrado, ErrorEsquema, ErrorEjecucion,
    ]
    try:
        from ultron.ia.errores import IAError
    except ImportError:
        pass
    else:
        tipos.append(IAError)
    return tuple(tipos)


def main() -> None:
    try:
        app()
    except _errores_conocidos() as e:
        t = tema.actual()
        t.error(str(e))
        sugerencia = getattr(e, "sugerencia", "")
        if sugerencia:
            t.info(sugerencia)
        sys.exit(2 if type(e).__name__ == "IANoConfigurada" else 1)
    except KeyboardInterrupt:
        tema.actual().consola.print("\n[apagado]Cancelado.[/]")
        sys.exit(130)
