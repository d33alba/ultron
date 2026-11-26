"""Biblioteca local y lanzadores de juegos."""

import difflib
import re
import shlex
import sqlite3
from configparser import ConfigParser, Error
from contextlib import closing
from dataclasses import dataclass
from pathlib import Path

from ultron.nucleo import rutas


@dataclass(frozen=True)
class Juego:
    nombre: str
    origen: str
    comando: tuple[str, ...]
    portada: str = ""


def vdf(texto: str) -> dict:
    """Lee el formato KeyValues de Steam, incluidos comentarios y escapes."""
    tokens = iter(re.findall(r'"(?:\\.|[^"\\])*"|//[^\n]*|[{}]|[^\s{}"]+', texto))

    def valor(token: str) -> str:
        return re.sub(r'\\(["\\])', r'\1', token[1:-1]) if token.startswith('"') else token

    def objeto(anidado: bool = False) -> dict:
        datos = {}
        for clave in tokens:
            if clave.startswith("//"):
                continue
            if clave == "}" and anidado:
                return datos
            siguiente = next((t for t in tokens if not t.startswith("//")), None)
            if clave in "{}" or siguiente in (None, "}"):
                raise ValueError("Archivo VDF incompleto.")
            datos[valor(clave)] = objeto(True) if siguiente == "{" else valor(siguiente)
        if anidado:
            raise ValueError("Falta cerrar un bloque VDF.")
        return datos

    return objeto()


def _archivo(ruta: Path) -> dict:
    try:
        return vdf(ruta.read_text(encoding="utf-8-sig", errors="replace"))
    except (OSError, ValueError, RecursionError):
        return {}


def steam(base: Path) -> list[Juego]:
    carpetas = {base}
    bibliotecas = _archivo(base / "libraryfolders.vdf").get("libraryfolders", {})
    if isinstance(bibliotecas, dict):
        for clave, entrada in bibliotecas.items():
            ruta = entrada.get("path") if isinstance(entrada, dict) else entrada
            if clave.isdigit() and ruta:
                carpetas.add(Path(ruta) / "steamapps")
    juegos = {}
    for carpeta in sorted(carpetas):
        for archivo in carpeta.glob("appmanifest_*.acf"):
            datos = _archivo(archivo).get("AppState", {})
            if not isinstance(datos, dict):
                continue
            appid = datos.get("appid", "")
            if isinstance(appid, str) and appid.isascii() and appid.isdigit() and datos.get("name"):
                juegos[appid] = Juego(datos["name"], "Steam", ("steam", f"steam://rungameid/{appid}"),
                                     appid)
    return list(juegos.values())


def lutris(archivo: Path) -> list[Juego]:
    if not archivo.is_file():
        return []
    try:
        with closing(sqlite3.connect(archivo.resolve().as_uri() + "?mode=ro", uri=True)) as con:
            filas = con.execute("SELECT id, name FROM games WHERE installed = 1").fetchall()
    except sqlite3.Error:
        return []
    return [Juego(nombre, "Lutris", ("lutris", f"lutris:rungameid/{id_juego}"))
            for id_juego, nombre in filas if nombre]


def desktop(archivo: Path) -> Juego | None:
    lector = ConfigParser(interpolation=None)
    try:
        lector.read(archivo, encoding="utf-8")
        ficha = lector["Desktop Entry"]
        if ("Game" not in ficha.get("Categories", "").split(";")
                or ficha.getboolean("Hidden", fallback=False)
                or ficha.get("Type", "Application") != "Application"):
            return None
        nombre = ficha.get("Name[es]", ficha.get("Name", archivo.stem))
        argumentos = shlex.split(ficha["Exec"])
    except (OSError, ValueError, KeyError, Error):
        return None
    if not argumentos:
        return None
    if Path(argumentos[0]).name == "flatpak" and "run" in argumentos[1:]:
        return Juego(nombre, "Flatpak", ("flatpak", "run", archivo.stem))
    return Juego(nombre, "Escritorio", ("gio", "launch", str(archivo)))


def detectar(ej) -> list[Juego]:
    datos = rutas.xdg_datos_raiz()
    juegos = steam(rutas.home() / ".steam/steam/steamapps")
    juegos.extend(steam(datos / "Steam/steamapps"))
    juegos.extend(lutris(datos / "lutris/pga.db"))
    instalados = None
    if ej.existe("flatpak"):
        resultado = ej.leer(["flatpak", "list", "--app", "--columns=application"])
        if resultado.ok:
            instalados = set(resultado.salida.split())
    carpetas = (datos / "applications", Path("/usr/share/applications"),
                datos / "flatpak/exports/share/applications",
                Path("/var/lib/flatpak/exports/share/applications"))
    for carpeta in carpetas:
        for archivo in sorted(carpeta.glob("*.desktop")):
            juego = desktop(archivo)
            if juego and (juego.origen != "Flatpak" or instalados is None
                          or archivo.stem in instalados):
                juegos.append(juego)
    unicos = {}
    for juego in juegos:
        unicos.setdefault(juego.nombre.casefold(), juego)
    return sorted(unicos.values(), key=lambda j: j.nombre.casefold())


def buscar(juegos: list[Juego], consulta: str) -> Juego | None:
    if consulta.isdecimal():
        indice = int(consulta) - 1
        return juegos[indice] if 0 <= indice < len(juegos) else None
    nombres = {j.nombre.casefold(): j for j in juegos}
    consulta = consulta.casefold().strip()
    parecido = difflib.get_close_matches(consulta, nombres, n=1, cutoff=0.5)
    return nombres.get(consulta) or (nombres[parecido[0]] if parecido else None)

