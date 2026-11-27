#!/usr/bin/env python3
"""Banco de pruebas real: ejecuta TODAS las funciones de Ultron en este equipo.

    python3 scripts/probar_funciones.py [--solo texto] [--ia]

Crea material de prueba (apuntes, PDF, foto con GPS, correo, presentación, carpeta
desordenada) en una carpeta temporal y lanza cada comando como lo haría una persona. Marca
FALLO si el comando revienta (traza de Python), termina con un código inesperado o tarda
demasiado. Las funciones interactivas se cortan a los pocos segundos y valen si no han
fallado. Sin `--ia`, las que usan IA deben avisar con claridad de que falta configurarla.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path

ULTRON = [sys.executable, "-m", "ultron"]


@dataclass
class Caso:
    argv: list[str]
    tipo: str = "ok"  # ok | ia | interactivo | red
    entrada: str = ""
    tiempo: int = 90
    codigos: tuple[int, ...] = (0,)
    nota: str = ""
    resultado: dict = field(default_factory=dict)


# ── material de prueba ─────────────────────────────────────────────────────────

APUNTES = """# La fotosíntesis

La fotosíntesis es el proceso por el que las plantas transforman la energía de la luz en
energía química. Ocurre en los cloroplastos, gracias a la clorofila.

## Fase luminosa
Se produce en los tilacoides. La luz rompe moléculas de agua (fotólisis), se libera oxígeno
y se forman ATP y NADPH.

## Fase oscura (ciclo de Calvin)
Ocurre en el estroma. Con el ATP y el NADPH se fija el CO2 y se forma glucosa.

## Importancia
Produce el oxígeno que respiramos y es la base de casi todas las cadenas alimentarias.
"""

DIAPOS = """# Ultron
## Un sistema que cambia de piel
---
# Modos
- Netanyahu
- Focus
- Gaming
---
# Gracias
"""

CORREO = """From: Banco <seguridad@banco-ejemplo.com>
To: alumno@example.com
Subject: Verifique su cuenta
Date: Fri, 27 Nov 2026 10:00:00 +0100
Received: from mail.example.net (mail.example.net [203.0.113.5])
Authentication-Results: mx.example.com; spf=fail; dkim=none; dmarc=fail

Pulse aqui para verificar: http://banco-ejemplo.xyz/login
"""


def pdf_con_texto(ruta: Path, texto: str) -> None:
    """PDF mínimo y válido con texto real extraíble (sin dependencias)."""
    lineas = [ln.replace("(", "[").replace(")", "]") for ln in texto.splitlines()]
    flujo = "BT /F1 11 Tf 50 800 Td 14 TL " + " ".join(
        f"({ln.encode('latin-1', 'replace').decode('latin-1')}) '" for ln in lineas) + " ET"
    objetos = [
        "<< /Type /Catalog /Pages 2 0 R >>",
        "<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Contents 4 0 R "
        "/Resources << /Font << /F1 5 0 R >> >> >>",
        f"<< /Length {len(flujo.encode('latin-1'))} >>\nstream\n{flujo}\nendstream",
        "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>",
    ]
    salida = b"%PDF-1.4\n"
    posiciones = []
    for i, obj in enumerate(objetos, 1):
        posiciones.append(len(salida))
        salida += f"{i} 0 obj\n{obj}\nendobj\n".encode("latin-1")
    xref = len(salida)
    salida += f"xref\n0 {len(objetos) + 1}\n0000000000 65535 f \n".encode()
    for p in posiciones:
        salida += f"{p:010d} 00000 n \n".encode()
    salida += (f"trailer\n<< /Size {len(objetos) + 1} /Root 1 0 R >>\n"
               f"startxref\n{xref}\n%%EOF\n").encode()
    ruta.write_bytes(salida)


def foto_con_gps(ruta: Path) -> None:
    from PIL import Image

    img = Image.new("RGB", (320, 200), (40, 90, 160))
    exif = Image.Exif()
    exif[0x010F] = "Ultron Cam"
    exif[0x0110] = "Modelo de prueba"
    gps = {1: "N", 2: (40.0, 25.0, 0.0), 3: "W", 4: (3.0, 42.0, 0.0)}
    exif[0x8825] = gps
    img.save(ruta, exif=exif)


def preparar(base: Path) -> dict[str, Path]:
    base.mkdir(parents=True, exist_ok=True)
    rutas = {
        "md": base / "fotosintesis.md", "pdf": base / "fotosintesis.pdf",
        "foto": base / "foto.jpg", "png": base / "imagen.png", "eml": base / "aviso.eml",
        "diapos": base / "charla.md", "desorden": base / "desorden",
    }
    rutas["md"].write_text(APUNTES, encoding="utf-8")
    pdf_con_texto(rutas["pdf"], APUNTES)
    foto_con_gps(rutas["foto"])
    from PIL import Image

    Image.new("RGB", (64, 64), (10, 200, 30)).save(rutas["png"])
    rutas["eml"].write_text(CORREO, encoding="utf-8")
    rutas["diapos"].write_text(DIAPOS, encoding="utf-8")
    rutas["desorden"].mkdir(exist_ok=True)
    for nombre, contenido in (("factura_luz.pdf", "x"), ("vacaciones.jpg", "x"),
                              ("tema1.docx", "x"), ("cancion.mp3", "x"), ("notas.txt", "hola")):
        (rutas["desorden"] / nombre).write_text(contenido)
    return rutas


# ── casos ──────────────────────────────────────────────────────────────────────


def casos(r: dict[str, Path]) -> list[Caso]:
    md, pdf, foto, png = str(r["md"]), str(r["pdf"]), str(r["foto"]), str(r["png"])
    C = Caso
    return [
        # núcleo y comunes
        C(["--version"]), C(["modos"]), C(["estado"]), C(["doctor", "--sin-ia"], codigos=(0, 1, 2)),
        C(["sistema"]), C(["ia", "estado"], codigos=(0, 2)),
        C(["tareas", "añadir", "Repasar fotosíntesis", "--para", "hoy"]),
        C(["tareas", "lista"]), C(["tareas", "hecha", "1"]), C(["tareas", "borrar", "1"]),
        C(["notas", "nueva", "Idea para la expo"]), C(["notas", "lista"]),
        C(["notas", "buscar", "expo"]), C(["notas", "ver", "1"]), C(["notas", "borrar", "1"]),
        C(["buscar", "clorofila", str(r["md"].parent), "--n", "3"]),
        C(["ordenar", str(r["desorden"]), "--sin-ia", "--si"]),
        C(["ordenar", str(r["desorden"]), "--deshacer"], codigos=(0, 1)),
        C(["explica-cmd", "tar -xzvf copia.tar.gz -C /tmp", "--sin-ia"]),
        C(["musica", "estado"]), C(["bienvenida"]),
        C(["ia", "preguntar", "¿Qué es Ubuntu?"], "ia"),
        C(["haz", "dime cuánto disco libre tengo"], "ia", entrada="n\n"),
        C(["error", "--sin-ejecutar"], "ia", codigos=(0, 1, 2)),
        C(["nexus", "--help"]),
        # NETANYAHU
        C(["osint", "fuentes"]),
        C(["osint", "dominio", "example.com"], "red"),
        C(["osint", "ip", "8.8.8.8"], "red"), C(["osint", "ip", "--demo", "8.8.8.8"]),
        C(["osint", "usuario", "ubuntu"], "red", tiempo=120),
        C(["osint", "meta", foto]), C(["osint", "meta", pdf]),
        C(["osint", "correo", str(r["eml"])], codigos=(0, 2)),
        C(["osint", "operacion", "example.com", "--no-abrir"], "red", tiempo=240),
        C(["osint", "url", "http://paypa1-secure.xyz/login"], "red", tiempo=120),
        C(["osint", "imagen", foto]),
        C(["osint", "huella", "--alias", "ultron-prueba-zz9", "--correo", "test@example.com"],
          "red", tiempo=240),
        C(["osint", "huella", "--alias", "x", "--para", "Ana"], entrada="n\n", codigos=(1,)),
        C(["radar", "--demo"]), C(["radar"], "red", tiempo=120, codigos=(0, 1, 2)),
        C(["auditar", "--sin-ia"], tiempo=120, entrada="y\n"),
        C(["web", "https://example.com"], "red", entrada="y\n"),
        C(["cve", "openssl"], "red", tiempo=180, codigos=(0, 1)),
        C(["ctf", "decodificar", "SG9sYSBVbHRyb24="]),
        C(["ctf", "codificar", "base64", "hola"]),
        C(["ctf", "hash", "5d41402abc4b2a76b9719d911017c592"]),
        C(["ctf", "estego", png]), C(["ctf", "archivo", "/bin/ls"]),
        C(["hackia", "¿tengo puertos abiertos?"], "ia", entrada="y\nn\n"),
        C(["ojo", "estado"]),
        # FOCUS
        C(["plan", "añadir", "Biología", "2026-12-18", "--temas", "3"]),
        C(["plan", "hoy"]), C(["plan", "lista"]), C(["plan", "ver"]), C(["plan", "proximo"]),
        C(["stats", "--demo"]), C(["stats"]), C(["flashcards", "lista"]),
        C(["resumen", pdf], "ia", tiempo=300), C(["resumen", md], "ia", tiempo=300),
        C(["flashcards", "crear", md, "--n", "5"], "ia", tiempo=300),
        C(["examen", md, "--n", "3"], "ia", tiempo=300, entrada="a\nb\nc\n"),
        C(["pregunta", pdf, "¿Dónde ocurre la fase oscura?"], "ia", tiempo=300),
        C(["esquema", md], "ia", tiempo=300),
        C(["explica", "fotólisis"], "ia", tiempo=300),
        C(["repasar", "--demo", "--sin-pausa"], "interactivo", tiempo=8),
        C(["pomodoro"], "interactivo", tiempo=6),
        # GAMING
        C(["juegos", "--demo"], "interactivo", tiempo=8), C(["perfil"]),
        C(["hud", "--demo", "--una-vez"]), C(["fps", "estado"], codigos=(0, 1, 2)),
        C(["gaming", "fondo"]), C(["turbo", "estado"], codigos=(0, 1, 2)),
        C(["visualizador"], "interactivo", tiempo=5, codigos=(0, 1, 2)),
        # PRESENTACIÓN
        C(["diapos", "--demo"], "interactivo", tiempo=6),
        C(["diapos", str(r["diapos"])], "interactivo", tiempo=6),
        C(["cronometro", "--demo"], "interactivo", tiempo=6),
        C(["teleprompter", str(r["diapos"])], "interactivo", tiempo=6),
        C(["ensayo", str(r["diapos"])], "ia", tiempo=300, entrada="respuesta\n" * 9),
        # FANTASMA
        C(["mac", "--demo"]), C(["dns-seguro", "--demo"]),
        C(["tor", "estado"], codigos=(0, 1, 2)),
        C(["limpiar-meta", foto]), C(["osint", "meta", foto]),
        C(["nota-efimera", "--min", "1"], "interactivo", tiempo=5, entrada="secreto\n"),
    ]


# ── ejecución ──────────────────────────────────────────────────────────────────

AVISOS_IA = ("ultron ia configurar", "Configura la IA", "IA sin configurar", "no hay IA")


def ejecutar(caso: Caso, con_ia: bool) -> dict:
    entorno = dict(os.environ, ULTRON_SIN_ANIMACIONES="1", NO_COLOR="1", COLUMNS="110",
                   PYTHONIOENCODING="utf-8")
    t0 = time.monotonic()
    try:
        r = subprocess.run(ULTRON + caso.argv, input=caso.entrada, capture_output=True,
                           text=True, timeout=caso.tiempo, env=entorno)
        salida, codigo, agotado = r.stdout + r.stderr, r.returncode, False
    except subprocess.TimeoutExpired as e:
        salida = (e.stdout or b"").decode(errors="replace") if isinstance(e.stdout, bytes) \
            else (e.stdout or "")
        salida += (e.stderr or b"").decode(errors="replace") if isinstance(e.stderr, bytes) \
            else (e.stderr or "")
        codigo, agotado = None, True
    dur = time.monotonic() - t0
    traza = "Traceback (most recent call last)" in salida
    if traza:
        estado = "FALLO"
    elif agotado:
        estado = "OK" if caso.tipo == "interactivo" else "LENTO"
    elif caso.tipo == "ia" and not con_ia:
        estado = "OK" if codigo == 2 and any(a in salida for a in AVISOS_IA) else (
            "OK" if codigo in caso.codigos else "FALLO")
    elif caso.tipo == "interactivo":
        estado = "OK" if codigo in (0, 130) + caso.codigos else "FALLO"
    else:
        estado = "OK" if codigo in caso.codigos else "FALLO"
    return {"estado": estado, "codigo": codigo, "segundos": round(dur, 1),
            "cola": "\n".join(salida.strip().splitlines()[-12:])}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--solo", default="", help="Solo los casos que contengan este texto.")
    ap.add_argument("--ia", action="store_true", help="Hay una IA configurada.")
    args = ap.parse_args()
    base = Path(tempfile.mkdtemp(prefix="ultron-pruebas-"))
    r = preparar(base)
    lista = [c for c in casos(r) if args.solo in " ".join(c.argv)]
    fallos = 0
    for c in lista:
        c.resultado = ejecutar(c, args.ia)
        e = c.resultado["estado"]
        fallos += e != "OK"
        print(f"{e:6} {c.resultado['segundos']:6.1f}s  ultron {' '.join(c.argv)}", flush=True)
        if e != "OK":
            print("        │ " + c.resultado["cola"].replace("\n", "\n        │ "), flush=True)
    print(f"\n{len(lista) - fallos}/{len(lista)} funciones correctas · material en {base}")
    return 1 if fallos else 0


if __name__ == "__main__":
    sys.exit(main())
