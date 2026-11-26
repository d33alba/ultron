"""Herramientas de codificación y análisis de archivos para retos."""

import base64
import binascii
import codecs
import math
import re
from collections import Counter
from pathlib import Path
from urllib.parse import quote, unquote

import typer
from PIL import Image, UnidentifiedImageError

from .comun import ejecutor, fallo, mostrar

app = typer.Typer(help="Codificación, identificación de huellas y análisis de archivos.")
ALFABETO = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
MORSE = dict(zip(ALFABETO, (
    ".- -... -.-. -.. . ..-. --. .... .. .--- -.- .-.. -- -. --- .--. --.- .-. ... - "
    "..- ...- .-- -..- -.-- --.. ----- .---- ..--- ...-- ....- ..... -.... --... ---.. ----."
).split(), strict=True))
INVERSO = {v: k for k, v in MORSE.items()}


def cesar(texto: str, giro: int) -> str:
    def desplazar(coincidencia: re.Match) -> str:
        letra = coincidencia[0]
        origen = ord("A" if letra.isupper() else "a")
        return chr(origen + (ord(letra) - origen + giro) % 26)

    return re.sub(r"[A-Za-z]", desplazar, texto)


def codificar_texto(tipo: str, texto: str) -> str:
    datos = texto.encode()
    bases = {"base64": base64.b64encode, "base32": base64.b32encode, "base85": base64.b85encode}
    if tipo in bases:
        return bases[tipo](datos).decode("ascii")
    if tipo == "hex":
        return datos.hex()
    if tipo == "binario":
        return " ".join(f"{b:08b}" for b in datos)
    if tipo == "url":
        return quote(texto, safe="")
    if tipo == "rot13":
        return codecs.encode(texto, "rot_13")
    if tipo == "morse":
        return " / ".join(" ".join(MORSE[c] for c in p) for p in texto.upper().split())
    if re.fullmatch(r"cesar:(?:[1-9]|1[0-9]|2[0-5])", tipo):
        return cesar(texto, int(tipo.split(":")[1]))
    raise ValueError("Tipo de codificación desconocido.")


def _puntuacion(texto: str) -> float:
    letras = [v for v in texto.lower() if "a" <= v <= "z"]
    if not letras:
        return -10
    palabras = re.findall(r"[a-z]+", texto.lower())
    comunes = set("hola mundo mensaje secreto esto prueba de la el en un una the and is hello "
                  "world secret message this test flag".split())
    frecuencia = "etaoinshrdlucmfwypvbgkjqxz"
    return (sum(frecuencia.index(v) + 1 if v in frecuencia else 26 for v in letras)
            / -len(letras) + 6 * len(comunes.intersection(palabras)))


def decodificar_texto(texto: str) -> list[tuple[str, str]]:
    limpio = "".join(texto.split())
    resultados = {}

    def ofrecer(tipo: str, resultado: str) -> None:
        if resultado and resultado != texto and all(
            c.isprintable() or c in "\n\t\r" for c in resultado
        ):
            if resultado not in resultados:
                resultados[resultado] = tipo

    bases = {
        "hex": lambda: bytes.fromhex(limpio),
        "base64": lambda: base64.b64decode(limpio + "=" * (-len(limpio) % 4), validate=True),
        "base32": lambda: base64.b32decode(limpio + "=" * (-len(limpio) % 8), casefold=True),
        "base85": lambda: base64.b85decode(limpio),
        "binario": lambda: bytes(int(limpio[i:i+8], 2) for i in range(0, len(limpio), 8))
        if re.fullmatch(r"(?:[01]{8})+", limpio) else b"",
    }
    for tipo, leer in bases.items():
        try:
            ofrecer(tipo, leer().decode("utf-8"))
        except (ValueError, binascii.Error):
            continue
    if re.search(r"%[\da-fA-F]{2}", texto):
        ofrecer("url", unquote(texto))
    try:
        ofrecer("morse", " ".join("".join(INVERSO[c] for c in p.split())
                                  for p in texto.split("/")))
    except KeyError:
        pass
    ofrecer("rot13", cesar(texto, 13))
    for giro in range(1, 26):
        ofrecer(f"césar +{giro}", cesar(texto, giro))
    return sorted(((tipo, valor) for valor, tipo in resultados.items()),
                  key=lambda par: _puntuacion(par[1]), reverse=True)


@app.command("codificar")
def cmd_codificar(tipo: str, texto: str) -> None:
    """Codifica texto en base64, base32, base85, hex, binario, URL, Morse, ROT13 o cesar:1–25."""
    try:
        resultado = codificar_texto(tipo.lower(), texto)
    except (KeyError, ValueError):
        fallo("Tipo de codificación o caracteres no admitidos.", 2)
    mostrar("CODIFICACIÓN", {"resultado": resultado})


@app.command("decodificar")
def cmd_decodificar(texto: str) -> None:
    """Prueba codificaciones y ordena las lecturas por probabilidad."""
    candidatos = decodificar_texto(texto)
    mostrar("DECODIFICACIÓN", {"más probable": candidatos[0] if candidatos else None,
                                "candidatos": candidatos[1:]})


@app.command("hash")
def cmd_hash(ctx: typer.Context, huella: str) -> None:
    """Identifica posibles algoritmos a partir del formato de una huella."""
    longitud = {32: "MD5, NTLM", 40: "SHA-1", 56: "SHA-224", 64: "SHA-256",
                96: "SHA-384", 128: "SHA-512"}
    tipo = longitud.get(len(huella)) if re.fullmatch("[a-fA-F0-9]+", huella) else None
    ej = ejecutor(ctx)
    if huella.startswith(("$2a$", "$2b$", "$2y$")):
        tipo = "bcrypt"
    datos = {"posibles algoritmos": tipo or "Desconocido"}
    if ej.existe("hashid") and not huella.startswith("-"):
        datos["hashid"] = ej.run(["hashid", huella], check=False).salida
    mostrar("HUELLA", datos)


def cadenas(datos: bytes) -> list[str]:
    return [m.decode("ascii")[:300] for m in re.findall(rb"[ -~]{4,}", datos)[:200]]


@app.command("archivo")
def cmd_archivo(archivo: Path = typer.Argument(..., exists=True, dir_okay=False)) -> None:
    """Muestra la firma, la entropía y cadenas de interés de un archivo."""
    try:
        with archivo.open("rb") as f:
            datos = f.read(4 * 1024 * 1024)
    except OSError:
        fallo("No se pudo leer el archivo.")
    firmas = {b"%PDF-": "PDF", b"\x89PNG": "PNG", b"\xff\xd8\xff": "JPEG",
              b"PK\x03\x04": "ZIP", b"\x7fELF": "ELF", b"GIF8": "GIF", b"\x1f\x8b": "gzip",
              b"MZ": "PE/DOS"}
    tipo = next((v for k, v in firmas.items() if datos.startswith(k)), "Desconocido")
    entropia = -sum(p * math.log2(p) for n in Counter(datos).values() if (p := n / len(datos)))
    interesantes = re.findall(rb"https?://[^\s\x00<>]{3,250}|flag\{[^}\r\n]{1,150}\}", datos, re.I)
    mostrar("ARCHIVO", {"tipo": tipo, "bytes analizados": len(datos),
                        "entropía": round(entropia, 3),
                        "cadenas": [c.decode("ascii", "replace") for c in interesantes[:30]]
                        or cadenas(datos)[:20]})


@app.command("estego")
def cmd_estego(ctx: typer.Context,
               archivo: Path = typer.Argument(..., exists=True, dir_okay=False)) -> None:
    """Inspecciona firmas y extrae los bits menos significativos de una imagen."""
    ej = ejecutor(ctx)
    ruta = str(archivo.resolve())
    datos = {}
    for comando in (["strings", "-n", "6", ruta], ["binwalk", ruta], ["steghide", "info", ruta]):
        if ej.existe(comando[0]):
            resultado = ej.run(comando, entrada="n\n", check=False, timeout=15)
            datos[comando[0]] = resultado.salida[:8000]
    try:
        with Image.open(archivo) as imagen:
            zona = imagen.crop((0, 0, min(512, imagen.width), min(512, imagen.height)))
            bajos = zona.convert("RGB").tobytes()
            decodificado = bytes(
                sum((b & 1) << (7 - bit) for bit, b in enumerate(bajos[i:i+8]))
                for i in range(0, len(bajos) - 7, 8)
            )
            datos["LSB"] = cadenas(decodificado)
    except (UnidentifiedImageError, OSError):
        datos["LSB"] = "Formato de imagen no reconocido."
    mostrar("ESTEGANOGRAFÍA", datos)
