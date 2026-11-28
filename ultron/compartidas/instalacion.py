"""`ultron instalar` y `ultron desinstalar`."""

from __future__ import annotations

import shutil
from pathlib import Path

import httpx
import typer

from ultron.nucleo import dependencias, jsonio, motor, rutas
from ultron.nucleo.ejecutor import Ejecutor, ErrorEjecucion
from ultron.nucleo.entorno import detectar
from ultron.ui import tema

app = typer.Typer()
EXT_API = "https://extensions.gnome.org/extension-info/"
EXT_BASE = "https://extensions.gnome.org"
PROPIA = "ultron@ultron"


def ruta_instaladas() -> Path:
    return rutas.datos() / "instaladas.json"


def _registrar_instalada(tipo: str, valor: str) -> None:
    datos = jsonio.leer(ruta_instaladas(), {}) or {}
    datos.setdefault(tipo, [])
    if valor not in datos[tipo]:
        datos[tipo].append(valor)
    jsonio.escribir(ruta_instaladas(), datos)


def dir_extension_propia() -> Path | None:
    for candidata in (rutas.paquete() / "_extension" / PROPIA,
                      rutas.paquete().parent / "extension" / PROPIA):
        if (candidata / "metadata.json").exists():
            return candidata
    return None


def descargar_extension(uuid: str, version_shell: str, destino: Path,
                        cliente: httpx.Client | None = None) -> Path:
    """Descarga el zip de una extensión compatible con esta versión de GNOME."""
    if (sin_red := rutas.offline()) is not None:
        local = sin_red / "extensiones" / version_shell / f"{uuid}.zip"
        if local.is_file():
            return local
    cliente = cliente or httpx.Client(timeout=30, follow_redirects=True)
    info = cliente.get(EXT_API, params={"uuid": uuid, "shell_version": version_shell})
    if info.status_code != 200:
        raise RuntimeError(f"{uuid}: no hay versión para GNOME {version_shell}")
    url = info.json().get("download_url")
    if not url:
        raise RuntimeError(f"{uuid}: sin enlace de descarga")
    zip_ = cliente.get(EXT_BASE + url)
    zip_.raise_for_status()
    destino.mkdir(parents=True, exist_ok=True)
    archivo = destino / f"{uuid}.zip"
    archivo.write_bytes(zip_.content)
    return archivo


def _instalar_voz(t: tema.Tema) -> None:
    """Voz neuronal de ULTRON (Piper). Si falla, queda espeak-ng: nunca para la instalación."""
    from ultron.nucleo import voz

    if voz._piper():
        t.ok("Voz de ULTRON lista")
        return
    try:
        with t.spinner_ctx("Descargando la voz de ULTRON (Piper, unos 80 MB)"):
            voz.instalar()
        t.ok("Voz de ULTRON lista")
    except Exception as e:  # noqa: BLE001
        t.aviso(f"No se pudo descargar la voz neuronal ({type(e).__name__}); "
                "se usará espeak-ng. Reintenta con: ultron voz instalar")


def _instalar_ojo(t: tema.Tema, ej: Ejecutor) -> None:
    """Deja el Ojo de Dios listo (Node 24 portátil + God's Eye View). Nunca es fatal."""
    from ultron.modos.netanyahu.funciones import ojo

    if (ojo.carpeta().parent / "instalado").is_file():
        t.ok("Ojo de Dios ya instalado")
        return
    try:
        ojo.preparar(ej, ojo.carpeta(), si=True)
        t.ok("Ojo de Dios listo")
    except (Exception, SystemExit) as e:  # noqa: BLE001
        t.aviso(f"El Ojo de Dios no se pudo preparar ahora ({type(e).__name__}); se "
                "instalará solo la primera vez que lo abras (ultron ojo).")


@app.command("instalar")
def cmd_instalar(
    modo: list[str] = typer.Option(None, "--modo", "-m", help="Solo lo de estos modos."),
    sin_apt: bool = typer.Option(False, "--sin-apt", help="No instales paquetes apt."),
    simular: bool = typer.Option(False, "--simular", help="Enseña lo que haría."),
    si: bool = typer.Option(False, "--si", "-y", help="No preguntes."),
) -> None:
    """Instala dependencias, extensiones de GNOME, fuentes y la extensión de Ultron (una vez)."""
    t = tema.actual()
    c = t.consola
    ej = Ejecutor(simular=simular, consola=c)
    plan = dependencias.plan(modo or None)
    paquetes = plan.apt.copy()
    if not sin_apt and (not modo or "gaming" in modo) and ej.existe("apt-cache"):
        for opcional in ("gpu-screen-recorder", "gpu-screen-recorder-cli"):
            disponible = ej.leer(["apt-cache", "show", opcional])
            if disponible.ok and f"Package: {opcional}" in disponible.salida.splitlines():
                paquetes.append(opcional)
                break
    from ultron.nucleo import herramientas
    from ultron.nucleo.entorno import puede_sudo

    gnome_ok = ej.existe("gnome-shell")
    paquetes = [p for p in paquetes if gnome_ok or p not in herramientas.SOLO_GNOME]
    faltan = herramientas.faltan(ej, paquetes)
    usb = herramientas.lista_usb(rutas.offline())
    con_apt = [] if sin_apt or not puede_sudo() else faltan
    tabla = t.tabla("Qué", "Cuántos", "Detalle", titulo="Ultron · instalación")
    tabla.add_row("Herramientas que faltan", str(len(faltan)), ", ".join(faltan[:10]) or "—")
    if faltan:
        tabla.add_row("Cómo", "", "apt (sudo)" if con_apt else
                      ("desde el USB, sin sudo" if usb else "no hay forma: ni sudo ni USB"))
    if ej.existe("gnome-extensions"):
        tabla.add_row("Extensiones GNOME", str(len(plan.extensiones) + 1),
                      ", ".join(u.split("@")[0] for u in plan.extensiones) + ", ultron")
    tabla.add_row("Fuentes", str(len(plan.fuentes)), ", ".join(plan.fuentes) or "—")
    c.print(tabla)
    if con_apt:
        t.info("Los paquetes apt necesitan sudo. Ocupan aproximadamente 300–600 MB.")
    if not simular and not si and not typer.confirm("¿Instalar?", default=True):
        raise typer.Exit(1)

    if con_apt:
        try:
            ej.run(["apt-get", "update"], sudo=True, check=False, timeout=None,
                   interactivo=True)
            ej.run(["apt-get", "install", "-y", *con_apt],
                   sudo=True, timeout=None, interactivo=True)
        except ErrorEjecucion as e:
            t.aviso(f"apt no ha podido instalarlo todo ({e}); pruebo con el USB.")
    _instalar_herramientas(t, ej, paquetes, simular)

    gnome = detectar(ej).gnome_mayor
    _instalar_extensiones(t, ej, plan.extensiones, str(gnome or 46))
    _instalar_propia(t, ej)
    _instalar_fuentes(t, ej, plan.fuentes)
    _generar_recursos(t, modo or None, simular)
    if not simular:
        _preparar_iconos(t, ej, modo or None)
    from ultron.capas.plasma import es_kde
    from ultron.nucleo import atajo

    kde = es_kde()
    if atajo.instalar(ej):
        t.ok("Meta+U y «Ultron NEXUS» en el menú" if kde else "Atajo Super+U para abrir Ultron")
    if not simular:
        _instalar_voz(t)
    if not simular and (not modo or "netanyahu" in modo):
        _instalar_ojo(t, ej)

    aviso = ("KDE Plasma: los modos cambian fondo, bloqueo, colores, iconos y música. "
             "Meta+U funciona tras volver a iniciar sesión.\n" if kde else
             "[bold]Cierra sesión y vuelve a entrar una vez[/] para que GNOME cargue las "
             "extensiones (en Wayland no se pueden cargar en caliente).\n")
    c.print(t.panel(aviso + "Después: [acento]ultron[/] o [acento]ultron entrar <modo>[/].",
                    titulo="Instalación terminada"))


def _instalar_herramientas(t: tema.Tema, ej: Ejecutor, paquetes: list[str],
                           simular: bool) -> None:
    """Lo que siga faltando tras apt sale del USB (sin sudo); el resto se explica."""
    from ultron.nucleo import herramientas as H

    faltan = H.faltan(ej, paquetes)
    if not faltan:
        t.ok(f"Herramientas del sistema: las {len(paquetes)} están")
        return
    offline = rutas.offline()
    hechos: list[str] = []
    if offline is not None and H.lista_usb(offline):
        try:
            with t.spinner_ctx(f"Instalando {len(faltan)} herramientas desde el USB (sin sudo)"):
                hechos, _ = H.instalar_desde_usb(ej, offline, faltan)
        except ErrorEjecucion as e:
            t.aviso(f"No se pudieron desempaquetar las herramientas: {e}")
        H.activar_path()
    if hechos:
        t.ok(f"Herramientas instaladas desde el USB: {', '.join(hechos)}")
    quedan = [p for p in faltan if p not in hechos]
    if simular or not quedan:
        return
    opcionales = [p for p in quedan if p in H.MOTIVO]
    for p in opcionales:
        t.info(f"{p}: no se instala ({H.MOTIVO[p]}). Es opcional.")
    reales = [p for p in quedan if p not in H.MOTIVO]
    if reales:
        t.aviso(f"Siguen faltando: {', '.join(reales)}. Con internet y sudo: "
                f"sudo apt install {' '.join(reales)}")


def _instalar_extensiones(t: tema.Tema, ej: Ejecutor, uuids: list[str], version: str) -> None:
    if not ej.existe("gnome-extensions"):
        from ultron.capas.plasma import es_kde

        if not es_kde():
            t.aviso("No está gnome-extensions: me salto las extensiones.")
        return
    cache = rutas.cache() / "extensiones"
    for uuid in uuids:
        info = ej.leer(["env", "LC_ALL=C", "gnome-extensions", "info", uuid])
        estado_ext = dependencias.interpretar_estado_extension(info)
        if info.ok and estado_ext not in {"OUT OF DATE", "OUT_OF_DATE", "ERROR"}:
            t.ok(f"{uuid} ya está instalada")
            continue
        if ej.simular:
            ej.historial.append(["#descargar-extension", uuid, version])
            continue
        try:
            with t.spinner_ctx(f"Descargando {uuid}"):
                zip_ = descargar_extension(uuid, version, cache)
            ej.run(["gnome-extensions", "install", "--force", str(zip_)])
            _registrar_instalada("extensiones", uuid)
            t.ok(f"{uuid} instalada")
        except (RuntimeError, ValueError, httpx.HTTPError, ErrorEjecucion) as e:
            t.aviso(f"{uuid}: {e}")


def _instalar_propia(t: tema.Tema, ej: Ejecutor) -> None:
    origen = dir_extension_propia()
    if origen is None:
        t.aviso("No encuentro la extensión de Ultron en el paquete.")
        return
    destino = rutas.xdg_datos_raiz() / "gnome-shell" / "extensions" / PROPIA
    ej.copiar(origen, destino)
    if ej.existe("gnome-extensions"):
        ej.run(["gnome-extensions", "enable", PROPIA], check=False)
    if not ej.simular:
        _registrar_instalada("extensiones", PROPIA)
    t.ok("Extensión de Ultron instalada (indicador, bocina y pomodoro en la barra)")


def _instalar_fuentes(t: tema.Tema, ej: Ejecutor, fuentes: list[str]) -> None:
    if not fuentes:
        return
    destino = rutas.xdg_datos_raiz() / "fonts" / "ultron"
    for nombre in fuentes:
        archivo = destino / f"{nombre}.ttf"
        if archivo.exists():
            continue
        if ej.simular:
            ej.historial.append(["#descargar-fuente", nombre])
            continue
        local = (rutas.offline() or Path("/nonexistent")) / "fuentes" / f"{nombre}.ttf"
        if local.is_file():
            destino.mkdir(parents=True, exist_ok=True)
            shutil.copy2(local, archivo)
            t.ok(f"Fuente {nombre}")
            continue
        try:
            r = httpx.get(dependencias.FUENTES[nombre], timeout=60, follow_redirects=True)
            r.raise_for_status()
            destino.mkdir(parents=True, exist_ok=True)
            archivo.write_bytes(r.content)
            t.ok(f"Fuente {nombre}")
        except httpx.HTTPError as e:
            t.aviso(f"Fuente {nombre}: {e}")
    if ej.existe("fc-cache"):
        ej.run(["fc-cache", str(destino)], check=False, fondo=True)


def _preparar_iconos(t: tema.Tema, ej: Ejecutor, modos: list[str] | None) -> None:
    """Genera ya los temas de iconos de cada modo (quedan en caché con su huella): así la
    primera vez que se entra en un modo tarda segundos y no medio minuto."""
    from ultron.capas.base import Contexto
    from ultron.capas.iconos import CapaIconos
    from ultron.nucleo import registro

    for m in registro.listar():
        cfg = m.capas.get("iconos")
        if (modos and m.id not in modos) or not cfg:
            continue
        capa = CapaIconos(ej, Contexto(modo=m, dir_modo=m.dir))
        if not capa.disponible()[0]:
            return
        try:
            with t.spinner_ctx(f"Preparando los iconos de {m.nombre}"):
                capa.preparar(cfg)
            t.ok(f"Iconos de {m.nombre} listos")
        except Exception as e:  # noqa: BLE001 - se generarán al entrar en el modo
            t.aviso(f"Iconos de {m.nombre}: se prepararán al entrar ({type(e).__name__})")


def _generar_recursos(t: tema.Tema, modos: list[str] | None, simular: bool) -> None:
    """Cada modo puede tener un generador de recursos (fondos, emblemas, sonidos…)."""
    import importlib

    from ultron.nucleo import registro

    for m in registro.listar():
        if modos and m.id not in modos:
            continue
        try:
            gen = importlib.import_module(f"ultron.modos.{m.id}.generar_recursos")
        except ImportError:
            continue
        if simular:
            continue
        with t.spinner_ctx(f"Generando recursos de {m.nombre}"):
            gen.generar()
        t.ok(f"Recursos de {m.nombre} listos")


@app.command("desinstalar")
def cmd_desinstalar(
    si: bool = typer.Option(False, "--si", "-y", help="No preguntes."),
    simular: bool = typer.Option(False, "--simular", help="Enseña lo que haría."),
) -> None:
    """Sale del modo, borra temas, iconos, sonidos, extensiones y configuración de Ultron."""
    t = tema.actual()
    ej = Ejecutor(simular=simular, consola=t.consola)
    if not simular and not si and not typer.confirm(
            "Se borrará todo lo que ha instalado Ultron. ¿Seguir?", default=False):
        raise typer.Exit(1)
    if motor.leer_instantanea():
        if any(r.estado == "fallida" for r in motor.salir(ej=ej)):
            t.error("La restauración quedó pendiente. Ejecuta: ultron salir")
            raise typer.Exit(1)
    from ultron.nucleo import atajo

    atajo.quitar(ej)
    from ultron.nucleo import herramientas

    herramientas.desinstalar(ej)
    instaladas = jsonio.leer(ruta_instaladas(), {}) or {}
    for uuid in instaladas.get("extensiones", []):
        ej.run(["gnome-extensions", "uninstall", uuid], check=False)
    datos = rutas.xdg_datos_raiz()
    for carpeta in ("themes", "icons", "sounds"):
        base = datos / carpeta
        if base.is_dir():
            for d in base.glob("Ultron-*"):
                ej.borrar(d)
    ej.borrar(datos / "fonts" / "ultron")
    from ultron.capas import shell

    bashrc = shell.ruta_bashrc()
    if bashrc.exists():
        texto = bashrc.read_text(encoding="utf-8")
        if shell.INICIO in texto:
            ej.escribir(bashrc, shell.quitar_bloque(texto))
    borrar_config = si or simular or typer.confirm(
        "¿Borrar también tu configuración (IA, notas, estadísticas)?", default=False)
    if borrar_config:
        for d in (rutas.config(), rutas.estado(), rutas.datos(), rutas.cache()):
            ej.borrar(d)
    if shutil.which("fc-cache") and not simular:
        ej.run(["fc-cache"], check=False, fondo=True)
    t.ok("Ultron desinstalado. Para quitar el programa: pipx uninstall ultron")
