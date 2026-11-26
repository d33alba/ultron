"""Lógica de privacidad del modo FANTASMA (sin interfaz): MAC, DNS, Tor, rastros, metadatos."""

from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from pathlib import Path

from ultron.nucleo import estado, rutas
from ultron.nucleo.ejecutor import Ejecutor

TIPOS_MAC = {"802-11-wireless": "wifi.cloned-mac-address",
             "802-3-ethernet": "ethernet.cloned-mac-address"}
RESOLVED = Path("/etc/systemd/resolved.conf.d/99-ultron.conf")
RESOLVED_CONF = (
    "# Generado por Ultron (modo fantasma)\n[Resolve]\n"
    "DNS=1.1.1.1#cloudflare-dns.com 9.9.9.9#dns.quad9.net\n"
    "FallbackDNS=1.0.0.1#cloudflare-dns.com 149.112.112.112#dns.quad9.net\n"
    "DNSOverTLS=yes\nDNSSEC=allow-downgrade\n"
)


class ErrorPrivacidad(Exception):
    pass


# --- MAC ---------------------------------------------------------------------------


@dataclass
class Conexion:
    nombre: str
    tipo: str
    dispositivo: str

    @property
    def clave(self) -> str:
        return TIPOS_MAC[self.tipo]


def conexion_activa(ej: Ejecutor) -> Conexion:
    if not ej.existe("nmcli"):
        raise ErrorPrivacidad("Falta NetworkManager (nmcli).")
    r = ej.leer(["nmcli", "-t", "-f", "NAME,TYPE,DEVICE", "connection", "show", "--active"])
    for linea in r.salida.splitlines():
        partes = linea.rsplit(":", 2)
        if len(partes) == 3 and partes[1] in TIPOS_MAC:
            return Conexion(partes[0].replace("\\:", ":"), partes[1], partes[2])
    raise ErrorPrivacidad("No hay ninguna conexión wifi o ethernet activa.")


def mac_aleatoria(ej: Ejecutor) -> Conexion:
    con = conexion_activa(ej)
    previo = ej.leer(["nmcli", "-g", con.clave, "connection", "show", con.nombre]).salida.strip()
    if not estado.obtener("fantasma_mac"):
        estado.actualizar(fantasma_mac={"conexion": con.nombre, "clave": con.clave,
                                        "previo": previo})
    ej.run(["nmcli", "connection", "modify", con.nombre, con.clave, "random"])
    ej.run(["nmcli", "connection", "up", con.nombre], check=False, timeout=60)
    return con


def mac_restaurar(ej: Ejecutor) -> bool:
    guardado = estado.obtener("fantasma_mac")
    if not guardado:
        return False
    ej.run(["nmcli", "connection", "modify", guardado["conexion"], guardado["clave"],
            guardado.get("previo") or ""])
    ej.run(["nmcli", "connection", "up", guardado["conexion"]], check=False, timeout=60)
    if not ej.simular:
        estado.actualizar(fantasma_mac=None)
    return True


def mac_actual(ej: Ejecutor, dispositivo: str) -> str:
    return ej.leer(["nmcli", "-g", "GENERAL.HWADDR", "device", "show", dispositivo]).salida \
        .strip().replace("\\", "")


# --- DNS ---------------------------------------------------------------------------------


def dns_on(ej: Ejecutor) -> None:
    ej.run(["mkdir", "-p", str(RESOLVED.parent)], sudo=True)
    ej.escribir(RESOLVED, RESOLVED_CONF, sudo=True)
    ej.run(["systemctl", "restart", "systemd-resolved"], sudo=True)


def dns_off(ej: Ejecutor) -> None:
    ej.borrar(RESOLVED, sudo=True)
    ej.run(["systemctl", "restart", "systemd-resolved"], sudo=True)


def dns_activo(ej: Ejecutor) -> bool:
    r = ej.leer(["resolvectl", "status"])
    return "+DNSOverTLS" in r.salida or "DNSOverTLS=yes" in r.salida


# --- Tor ----------------------------------------------------------------------------------


def tor_comprobar(ej: Ejecutor) -> dict:
    if not ej.existe("torsocks") or not ej.existe("curl"):
        raise ErrorPrivacidad("Falta torsocks o curl: sudo apt install torsocks curl")
    r = ej.run(["torsocks", "curl", "-s", "--max-time", "20",
                "https://check.torproject.org/api/ip"], check=False, timeout=30)
    try:
        return json.loads(r.salida)
    except ValueError as e:
        raise ErrorPrivacidad("Tor no responde. ¿Está arrancado? ultron tor on") from e


# --- rastros ----------------------------------------------------------------------------------


@dataclass
class Rastro:
    nombre: str
    rutas: list[Path]
    comando: list[str] | None = None
    sudo: bool = False

    def tamano(self) -> int:
        total = 0
        for r in self.rutas:
            if r.is_file():
                total += r.stat().st_size
            elif r.is_dir():
                total += sum(f.stat().st_size for f in r.rglob("*") if f.is_file())
        return total


def rastros(incluir_sudo: bool = False) -> list[Rastro]:
    """Lista CERRADA de rastros. Nunca incluye documentos del usuario."""
    h = rutas.home()
    datos = rutas.xdg_datos_raiz()
    cache = Path(rutas.cache()).parent
    lista = [
        Rastro("Archivos recientes", [datos / "recently-used.xbel"]),
        Rastro("Miniaturas", [cache / "thumbnails"]),
        Rastro("Historial de bash", [h / ".bash_history"]),
        Rastro("Historial de Python", [h / ".python_history"]),
        Rastro("Papelera", [datos / "Trash" / "files", datos / "Trash" / "info"]),
        Rastro("Registros del usuario", [],
               ["journalctl", "--user", "--rotate", "--vacuum-time=1s"]),
    ]
    if incluir_sudo:
        lista.append(Rastro("Caché de apt", [], ["apt-get", "clean"], sudo=True))
    return lista


def borrar_rastros(ej: Ejecutor, lista: list[Rastro]) -> list[str]:
    hechos = []
    for r in lista:
        for ruta in r.rutas:
            if ruta.name in ("files", "info") and ruta.parent.name == "Trash":
                if ruta.exists():
                    for hijo in ruta.iterdir():
                        ej.borrar(hijo)
            elif ruta.exists():
                ej.borrar(ruta)
        if r.comando and ej.existe(r.comando[0]):
            ej.run(r.comando, sudo=r.sudo, check=False)
        hechos.append(r.nombre)
    return hechos


# --- metadatos -----------------------------------------------------------------------------------


def contar_metadatos(archivo: Path) -> int:
    sufijo = archivo.suffix.lower()
    try:
        if sufijo in (".jpg", ".jpeg", ".png", ".webp", ".tif", ".tiff"):
            from PIL import Image

            with Image.open(archivo) as img:
                return len(img.getexif()) + len(img.info.get("exif", b"")) // 64 + \
                    sum(k not in ("dpi", "exif") for k in img.info)
        if sufijo == ".pdf":
            from pypdf import PdfReader

            return len(PdfReader(str(archivo)).metadata or {})
    except Exception:  # noqa: BLE001
        return 0
    return 0


def limpiar_metadatos(ej: Ejecutor, archivo: Path) -> str:
    """Quita los metadatos en el propio archivo. Devuelve el método usado."""
    if ej.existe("mat2"):
        ej.run(["mat2", "--inplace", str(archivo)])
        return "mat2"
    sufijo = archivo.suffix.lower()
    if sufijo in (".jpg", ".jpeg", ".png", ".webp", ".tif", ".tiff"):
        from PIL import Image

        with Image.open(archivo) as img:
            limpia = Image.new(img.mode, img.size)
            limpia.putdata(list(img.getdata()))
            formato = img.format
        temporal = archivo.with_suffix(archivo.suffix + ".tmp")
        limpia.save(temporal, format=formato)
        shutil.move(str(temporal), str(archivo))
        return "pillow"
    if sufijo == ".pdf":
        from pypdf import PdfReader, PdfWriter

        lector = PdfReader(str(archivo))
        escritor = PdfWriter()
        for pagina in lector.pages:
            escritor.add_page(pagina)
        escritor.add_metadata({"/Producer": ""})
        temporal = archivo.with_suffix(".pdf.tmp")
        with open(temporal, "wb") as f:
            escritor.write(f)
        shutil.move(str(temporal), str(archivo))
        return "pypdf"
    raise ErrorPrivacidad(f"No sé limpiar {sufijo} sin mat2 (sudo apt install mat2).")


# --- cifrado -------------------------------------------------------------------------------------


def comando_cifrar(ej: Ejecutor, archivo: Path) -> tuple[list[str], Path]:
    if ej.existe("age"):
        destino = archivo.with_name(archivo.name + ".age")
        return ["age", "-p", "-o", str(destino), str(archivo)], destino
    if ej.existe("gpg"):
        destino = archivo.with_name(archivo.name + ".gpg")
        return ["gpg", "--symmetric", "--cipher-algo", "AES256", "-o", str(destino),
                str(archivo)], destino
    raise ErrorPrivacidad("Falta age o gpg: sudo apt install age")


def comando_descifrar(archivo: Path) -> tuple[list[str], Path]:
    if archivo.suffix == ".age":
        destino = archivo.with_suffix("")
        return ["age", "-d", "-o", str(destino), str(archivo)], destino
    if archivo.suffix == ".gpg":
        destino = archivo.with_suffix("")
        return ["gpg", "-d", "-o", str(destino), str(archivo)], destino
    raise ErrorPrivacidad("Solo sé descifrar archivos .age o .gpg.")


def dir_cofre_cifrado() -> Path:
    return rutas.datos() / "cofre"


def punto_montaje() -> Path:
    return rutas.home() / "Cofre"
