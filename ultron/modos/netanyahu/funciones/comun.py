"""Contexto de ejecución y presentación de operaciones."""

import json
import re
import sys
import tempfile
from datetime import datetime
from pathlib import Path

import httpx
import typer
from rich.text import Text

from ultron.nucleo import config, rutas
from ultron.nucleo.ejecutor import Ejecutor
from ultron.ui.tema import cargar_tema, soporta_unicode

ASCII = str.maketrans({"◉": "o", "✡": "*", "◆": "R", "·": ".", "▓": "#", "▒": "+",
                      "░": ".", "█": "#", "─": "-", "│": "|"})


def interfaz():
    return cargar_tema("netanyahu")


def texto_terminal(texto: str) -> str:
    if soporta_unicode():
        return texto
    codificacion = getattr(sys.stdout, "encoding", None) or "ascii"
    return texto.translate(ASCII).encode(codificacion, "replace").decode(codificacion)


def ejecutor(ctx: typer.Context) -> Ejecutor:
    return Ejecutor(simular=bool(ctx.find_root().params.get("simular")),
                    consola=interfaz().consola)


def fallo(mensaje: str, codigo: int = 1) -> None:
    interfaz().consola.print(Text(mensaje, style="error"))
    raise typer.Exit(codigo)


def permiso(ej: Ejecutor) -> None:
    if ej.simular or config.obtener("netanyahu", "aviso_aceptado", False):
        return
    t = interfaz()
    t.consola.print(t.panel("Solo en tu red, tu equipo o con permiso escrito.",
                            titulo="AVISO DE USO", border_style="error"))
    if not typer.confirm("¿Aceptas el aviso?"):
        raise typer.Exit(1)
    config.fijar("netanyahu", "aviso_aceptado", True)


def requerir(ej: Ejecutor, programa: str, paquete: str | None = None) -> None:
    if not ej.existe(programa):
        fallo(f"Falta {programa}. Instala el paquete apt {paquete or programa}.", 2)


def mostrar(titulo: str, datos: dict, crudo: bool = False) -> None:
    t = interfaz()
    if crudo:
        t.consola.print_json(data=datos, ensure_ascii=not soporta_unicode())
        return
    lineas = Text()
    for clave, valor in datos.items():
        if valor in ("", [], {}):
            continue
        lineas.append(f"{t.glifo('info')} {clave.upper()}  ", style="acento")
        if isinstance(valor, str):
            texto = valor
        elif isinstance(valor, list) and all(isinstance(x, (str, int, float)) for x in valor):
            texto = "".join(f"\n   • {x}" for x in valor)
        elif isinstance(valor, dict) and all(not isinstance(x, (dict, list))
                                             for x in valor.values()):
            texto = "".join(f"\n   {k}: {v}" for k, v in valor.items())
        else:
            texto = json.dumps(valor, ensure_ascii=False, indent=2)
        lineas.append(texto_terminal(f"{texto}\n"))
    t.consola.print(t.panel(lineas, titulo=f"INFORME {titulo}"))


def guardar(objetivo: str, datos: dict, ej: Ejecutor) -> Path | None:
    if ej.simular:
        return None
    raiz = rutas.asegurar(rutas.documentos() / "operaciones")
    nombre = re.sub(r"[^a-zA-Z0-9_-]", "-", objetivo)[:70]
    fecha = datetime.now().strftime("%Y%m%d-%H%M%S")
    carpeta = Path(tempfile.mkdtemp(prefix=f"{fecha}-{nombre}-", dir=raiz))
    ej.escribir(carpeta / "datos.json", json.dumps(datos, ensure_ascii=False, indent=2), modo=0o600)
    ej.escribir(rutas.estado() / "netanyahu.operacion", nombre, modo=0o600)
    return carpeta


def consultar(cliente: httpx.Client, metodo: str, url: str, **kw) -> dict | list:
    respuesta = cliente.request(metodo, url, **kw)
    respuesta.raise_for_status()
    datos = respuesta.json()
    if not isinstance(datos, (dict, list)):
        raise ValueError("La respuesta no contiene datos estructurados.")
    return datos
