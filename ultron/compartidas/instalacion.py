"""`ultron instalar` y `ultron desinstalar`."""

from __future__ import annotations

import shutil
from pathlib import Path

import httpx
import typer

from ultron.nucleo import dependencias, jsonio, motor, rutas
from ultron.nucleo.ejecutor import Ejecutor
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
    faltan_apt = [] if sin_apt else dependencias.apt_faltan(ej, paquetes)
    tabla = t.tabla("Qué", "Cuántos", "Detalle", titulo="Ultron · instalación")
    tabla.add_row("Paquetes apt", str(len(faltan_apt)), ", ".join(faltan_apt[:10]) or "—")
    tabla.add_row("Extensiones GNOME", str(len(plan.extensiones) + 1),
                  ", ".join(u.split("@")[0] for u in plan.extensiones) + ", ultron")
    tabla.add_row("Fuentes", str(len(plan.fuentes)), ", ".join(plan.fuentes) or "—")
    c.print(tabla)
    if faltan_apt:
        t.info("Los paquetes apt necesitan sudo. Ocupan aproximadamente 300–600 MB.")
    if not simular and not si and not typer.confirm("¿Instalar?", default=True):
        raise typer.Exit()

    if faltan_apt:
        ej.run(["sudo", "apt-get", "update"], check=False, timeout=None)
        ej.run(["sudo", "apt-get", "install", "-y", *faltan_apt], check=False, timeout=None)

    gnome = detectar(ej).gnome_mayor
    _instalar_extensiones(t, ej, plan.extensiones, str(gnome or 46))
    _instalar_propia(t, ej)
    _instalar_fuentes(t, ej, plan.fuentes)
    _generar_recursos(t, modo or None, simular)
    if not simular and (not modo or "netanyahu" in modo):
        from ultron.modos.netanyahu.funciones.ojo import version_valida

        if not ej.existe("node") or not version_valida(ej.leer(["node", "--version"]).salida):
            t.aviso("Ojo de Dios requiere Node 24.14+ de la rama 24 o Node 26. "
                    "Ejecuta ultron ojo instalar para comprobar las opciones de instalación.")

    c.print(t.panel(
        "[bold]Cierra sesión y vuelve a entrar una vez[/] para que GNOME cargue las "
        "extensiones (en Wayland no se pueden cargar en caliente).\n"
        "Después: [acento]ultron[/] o [acento]ultron entrar <modo>[/].",
        titulo="Instalación terminada",
    ))


def _instalar_extensiones(t: tema.Tema, ej: Ejecutor, uuids: list[str], version: str) -> None:
    if not ej.existe("gnome-extensions"):
        t.aviso("No está gnome-extensions: me salto las extensiones.")
        return
    cache = rutas.cache() / "extensiones"
    for uuid in uuids:
        if ej.leer(["gnome-extensions", "info", uuid]).codigo == 0:
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
        except (RuntimeError, httpx.HTTPError) as e:
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
        try:
            r = httpx.get(dependencias.FUENTES[nombre], timeout=60, follow_redirects=True)
            r.raise_for_status()
            destino.mkdir(parents=True, exist_ok=True)
            archivo.write_bytes(r.content)
            t.ok(f"Fuente {nombre}")
        except httpx.HTTPError as e:
            t.aviso(f"Fuente {nombre}: {e}")
    if ej.existe("fc-cache"):
        ej.run(["fc-cache", "-f"], check=False, timeout=180)


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
        raise typer.Exit()
    if motor.leer_instantanea():
        motor.salir(ej=ej)
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
        ej.run(["fc-cache", "-f"], check=False)
    t.ok("Ultron desinstalado. Para quitar el programa: pipx uninstall ultron")
