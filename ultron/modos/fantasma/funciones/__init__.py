"""Comandos del modo FANTASMA: mac, dns-seguro, tor, rastros, limpiar-meta, cofre, efímero."""

from __future__ import annotations

import os
import secrets
import subprocess
import tempfile
import time
from pathlib import Path

import typer
from rich.live import Live
from rich.text import Text

from ultron.modos.fantasma import privacidad as P
from ultron.nucleo.ejecutor import Ejecutor, ErrorEjecucion
from ultron.ui import tema

app = typer.Typer()


def _t() -> tema.Tema:
    return tema.cargar_tema("fantasma")


def _ej(ctx: typer.Context | None = None) -> Ejecutor:
    simular = bool(ctx and ctx.find_root().params.get("simular"))
    return Ejecutor(simular=simular, consola=_t().consola)


def _fallo(e: Exception) -> None:
    _t().error(str(e))
    raise typer.Exit(1)


def _tamano(n: int) -> str:
    for u in ("B", "KB", "MB", "GB"):
        if n < 1024:
            return f"{n:.0f} {u}"
        n /= 1024
    return f"{n:.1f} TB"


# --- MAC -------------------------------------------------------------------------------


@app.command("mac")
def cmd_mac(
    ctx: typer.Context,
    accion: str = typer.Argument("estado", help="aleatoria, restaurar o estado."),
) -> None:
    """MAC aleatoria en tu conexión (la red no te reconoce). Corta la red unos segundos."""
    t, ej = _t(), _ej(ctx)
    try:
        if accion == "aleatoria":
            t.aviso("la conexión se cortará unos segundos…")
            con = P.mac_aleatoria(ej)
            t.ok(f"MAC aleatoria en «{con.nombre}»: {P.mac_actual(ej, con.dispositivo) or '?'}")
        elif accion == "restaurar":
            t.ok("MAC original restaurada.") if P.mac_restaurar(ej) else t.info(
                "no había nada que restaurar.")
        else:
            con = P.conexion_activa(ej)
            t.info(f"{con.nombre} ({con.dispositivo}) · MAC {P.mac_actual(ej, con.dispositivo)}")
    except (P.ErrorPrivacidad, ErrorEjecucion) as e:
        _fallo(e)


# --- DNS -------------------------------------------------------------------------------


@app.command("dns-seguro")
def cmd_dns(
    ctx: typer.Context,
    accion: str = typer.Argument("estado", help="on, off o estado."),
) -> None:
    """DNS cifrado (DNS sobre TLS con Cloudflare y Quad9) en systemd-resolved."""
    t, ej = _t(), _ej(ctx)
    try:
        if accion == "on":
            P.dns_on(ej)
            t.ok("DNS cifrado activado… tu proveedor ya no ve qué webs visitas.")
        elif accion == "off":
            P.dns_off(ej)
            t.ok("DNS normal restaurado.")
        else:
            t.info("DNS sobre TLS: " + ("activo" if P.dns_activo(ej) else "no activo"))
    except ErrorEjecucion as e:
        _fallo(e)


# --- Tor -------------------------------------------------------------------------------


@app.command("tor")
def cmd_tor(
    ctx: typer.Context,
    accion: str = typer.Argument("estado", help="on, off, estado o navegador."),
) -> None:
    """Arranca Tor y comprueba que tu tráfico sale por la red Tor."""
    t, ej = _t(), _ej(ctx)
    try:
        if accion == "on":
            ej.run(["systemctl", "start", "tor"], sudo=True)
            t.ok("tor arrancado. comprueba con: ultron tor estado")
        elif accion == "off":
            ej.run(["systemctl", "stop", "tor"], sudo=True)
            t.ok("tor parado.")
        elif accion == "navegador":
            if not ej.existe("torbrowser-launcher"):
                _fallo(P.ErrorPrivacidad("Instala: sudo apt install torbrowser-launcher"))
            ej.run(["torbrowser-launcher"], fondo=True)
        else:
            with t.spinner_ctx("preguntando a check.torproject.org"):
                datos = P.tor_comprobar(ej)
            if datos.get("IsTor"):
                t.ok(f"sales por Tor… IP visible: {datos.get('IP')}")
            else:
                t.aviso(f"NO estás usando Tor (IP {datos.get('IP')}).")
    except (P.ErrorPrivacidad, ErrorEjecucion) as e:
        _fallo(e)


# --- rastros -------------------------------------------------------------------------------


@app.command("rastros")
def cmd_rastros(
    ctx: typer.Context,
    con_sudo: bool = typer.Option(False, "--con-sudo", help="Incluye la caché de apt."),
    si: bool = typer.Option(False, "--si", "-y", help="No preguntes."),
) -> None:
    """Borra rastros locales (recientes, miniaturas, historiales, papelera). Nunca documentos."""
    t, ej = _t(), _ej(ctx)
    lista = P.rastros(con_sudo)
    tabla = t.tabla("Rastro", "Tamaño", "Qué se borra")
    for r in lista:
        detalle = ", ".join(str(p).replace(str(Path.home()), "~") for p in r.rutas) or \
            " ".join(r.comando or [])
        tabla.add_row(r.nombre, _tamano(r.tamano()), detalle)
    t.consola.print(tabla)
    if ej.simular:
        return
    if not si and not typer.confirm("¿borrar todo esto? no se puede deshacer", default=False):
        return
    P.borrar_rastros(ej, lista)
    t.ok(t.frase("ok", "hecho… sin dejar rastro."))


# --- metadatos -------------------------------------------------------------------------------


@app.command("limpiar-meta")
def cmd_limpiar_meta(
    ctx: typer.Context,
    destino: Path = typer.Argument(..., exists=True, help="Archivo o carpeta."),
) -> None:
    """Quita los metadatos (GPS, cámara, autor…) de fotos y PDF."""
    t, ej = _t(), _ej(ctx)
    archivos = [destino] if destino.is_file() else sorted(
        p for p in destino.rglob("*") if p.is_file())
    tabla = t.tabla("Archivo", "Antes", "Después", "Método")
    for f in archivos:
        antes = P.contar_metadatos(f)
        try:
            metodo = P.limpiar_metadatos(ej, f)
        except (P.ErrorPrivacidad, ErrorEjecucion, OSError) as e:
            tabla.add_row(f.name, str(antes), "—", f"[error]{e}[/]")
            continue
        tabla.add_row(f.name, str(antes), str(P.contar_metadatos(f)), metodo)
    t.consola.print(tabla)


# --- cofre -----------------------------------------------------------------------------------

cofre = typer.Typer(help="Cifrado: archivos sueltos y una carpeta-cofre cifrada.",
                    no_args_is_help=True)
app.add_typer(cofre, name="cofre")


@cofre.command("cifrar")
def cmd_cifrar(archivo: Path = typer.Argument(..., exists=True, dir_okay=False)) -> None:
    """Cifra un archivo con contraseña (age o gpg)."""
    t, ej = _t(), _ej()
    try:
        cmd, destino = P.comando_cifrar(ej, archivo)
        subprocess.call(cmd)
    except P.ErrorPrivacidad as e:
        _fallo(e)
    if destino.exists():
        t.ok(f"cifrado: {destino.name}. borra el original con: shred -u {archivo.name}")


@cofre.command("descifrar")
def cmd_descifrar(archivo: Path = typer.Argument(..., exists=True, dir_okay=False)) -> None:
    """Descifra un archivo .age o .gpg."""
    try:
        cmd, destino = P.comando_descifrar(archivo)
    except P.ErrorPrivacidad as e:
        _fallo(e)
    subprocess.call(cmd)
    if destino.exists():
        _t().ok(f"descifrado: {destino.name}")


def _con_gocryptfs(ej: Ejecutor) -> bool:
    return ej.existe("gocryptfs")


@cofre.command("crear")
def cmd_crear() -> None:
    """Crea la carpeta cifrada (gocryptfs si está; si no, un tar cifrado)."""
    t, ej = _t(), _ej()
    cifrado = P.dir_cofre_cifrado()
    if _con_gocryptfs(ej):
        if (cifrado / "gocryptfs.conf").exists():
            t.info("el cofre ya existe. ábrelo con: ultron cofre abrir")
            return
        cifrado.mkdir(parents=True, exist_ok=True)
        subprocess.call(["gocryptfs", "-init", str(cifrado)])
    else:
        P.punto_montaje().mkdir(exist_ok=True)
        t.info(f"sin gocryptfs: guarda tus archivos en {P.punto_montaje()} y ejecuta "
               "«ultron cofre cerrar» para cifrarlos.")
        return
    t.ok("cofre creado. ábrelo con: ultron cofre abrir")


@cofre.command("abrir")
def cmd_abrir() -> None:
    """Monta el cofre en ~/Cofre."""
    t, ej = _t(), _ej()
    montaje = P.punto_montaje()
    montaje.mkdir(exist_ok=True)
    if _con_gocryptfs(ej):
        subprocess.call(["gocryptfs", str(P.dir_cofre_cifrado()), str(montaje)])
    else:
        paquete = P.dir_cofre_cifrado().with_suffix(".tar.gpg")
        if not paquete.exists():
            _fallo(P.ErrorPrivacidad("no hay cofre. créalo con: ultron cofre crear"))
        subprocess.call(["bash", "-c", 'gpg -d "$1" | tar -x -C "$2"', "_",
                         str(paquete), str(montaje)])
    t.ok(f"cofre abierto en {montaje}. ciérralo con: ultron cofre cerrar")


@cofre.command("cerrar")
def cmd_cerrar() -> None:
    """Desmonta (o cifra y borra) el cofre."""
    t, ej = _t(), _ej()
    montaje = P.punto_montaje()
    if _con_gocryptfs(ej):
        ej.run(["fusermount", "-u", str(montaje)], check=False)
    else:
        paquete = P.dir_cofre_cifrado().with_suffix(".tar.gpg")
        paquete.parent.mkdir(parents=True, exist_ok=True)
        codigo = subprocess.call(
            ["bash", "-c", 'tar -C "$1" -c . | gpg --symmetric --cipher-algo AES256 -o "$2"',
             "_", str(montaje), str(paquete)])
        if codigo != 0:
            _fallo(P.ErrorPrivacidad("no se pudo cifrar el cofre; tus archivos siguen ahí."))
        for f in montaje.rglob("*"):
            if f.is_file():
                ej.run(["shred", "-u", "-z", str(f)], check=False)
    t.ok("cofre cerrado…")


# --- efímero ----------------------------------------------------------------------------------


def base_efimera() -> Path:
    shm = Path("/dev/shm")
    return shm if shm.is_dir() else Path(tempfile.gettempdir())


@app.command("efimero")
def cmd_efimero() -> None:
    """Abre una shell en una carpeta en memoria que se destruye al salir (exit)."""
    t, ej = _t(), _ej()
    carpeta = Path(tempfile.mkdtemp(prefix="ultron-efimero-", dir=base_efimera()))
    t.info(f"carpeta efímera: {carpeta}. escribe «exit» para destruirla.")
    entorno = {**os.environ, "HISTFILE": "/dev/null", "ULTRON_EFIMERO": "1"}
    try:
        subprocess.call([os.environ.get("SHELL", "bash")], cwd=carpeta, env=entorno)
    finally:
        for f in carpeta.rglob("*"):
            if f.is_file() and ej.existe("shred"):
                ej.run(["shred", "-u", "-z", str(f)], check=False)
        ej.borrar(carpeta)
        t.ok("destruida… como si nunca hubiera existido.")


@app.command("nota-efimera")
def cmd_nota(
    minutos: float = typer.Option(1, "--min", help="Minutos antes de destruirse."),
) -> None:
    """Nota que solo existe en memoria y se autodestruye (línea con un punto para terminar)."""
    t = _t()
    t.consola.print("[apagado]escribe la nota. una línea con «.» para terminar.[/]")
    lineas = []
    while True:
        try:
            linea = input()
        except EOFError:
            break
        if linea.strip() == ".":
            break
        lineas.append(linea)
    clave = secrets.token_bytes(32)
    datos = "\n".join(lineas).encode()
    oculta = bytes(b ^ clave[i % 32] for i, b in enumerate(datos))
    del datos, lineas
    fin = time.monotonic() + minutos * 60
    try:
        with Live(console=t.consola, screen=True, refresh_per_second=2) as live:
            while (restante := fin - time.monotonic()) > 0:
                texto = bytes(b ^ clave[i % 32] for i, b in enumerate(oculta)).decode()
                live.update(t.panel(Text(texto), titulo=f"se destruye en {int(restante)} s"))
                time.sleep(0.5)
    except KeyboardInterrupt:
        pass
    oculta = b"\x00" * len(oculta)
    t.ok("la nota ya no existe…")
