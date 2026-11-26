"""Motor seguro de "lenguaje natural → comandos de Ubuntu" y el comando `ultron haz`.

La IA propone pasos en JSON; cada comando se evalúa (patrones destructivos bloqueados),
se enseña y solo se ejecuta si el usuario lo confirma, uno a uno.
"""

from __future__ import annotations

import re
import shlex
from collections.abc import Callable
from dataclasses import dataclass

import typer
from rich.text import Text

from ultron.ia.util import pedir_json
from ultron.nucleo.ejecutor import Ejecutor
from ultron.ui import tema

app = typer.Typer()

BLOQUEADOS: list[tuple[str, str]] = [
    (r"\brm\s+(-[a-zA-Z]*[rf][a-zA-Z]*\s+)+(/|/\*|~|\$HOME|/home|/etc|/usr|/boot|/var)(\s|$)",
     "borrado recursivo de una carpeta del sistema"),
    (r"\brm\s+.*--no-preserve-root", "borrado de la raíz"),
    (r"\bmkfs(\.\w+)?\b", "formatear un disco"),
    (r"\bdd\b.*\bof=/dev/(sd|nvme|hd|mmcblk|vd)", "escribir directamente en un disco"),
    (r":\(\)\s*\{\s*:\|:&\s*\};:", "fork bomb"),
    (r"\bchmod\s+(-R\s+)?[0-7]*777\s+/(\s|$)", "permisos 777 en todo el sistema"),
    (r"\bchown\s+-R\s+\S+\s+/(\s|$)", "cambiar el dueño de todo el sistema"),
    (r"(curl|wget)\b[^|]*\|\s*(sudo\s+)?(ba|z|da)?sh\b", "ejecutar un script descargado"),
    (r">\s*/dev/(sd|nvme|hd|mmcblk)", "sobrescribir un disco"),
    (r"\b(shutdown|poweroff|reboot|halt)\b", "apagar o reiniciar el equipo"),
    (r"\bmv\s+(/|/\*)\s", "mover la raíz del sistema"),
    (r"\bcrontab\s+-r\b", "borrar todas las tareas programadas"),
    (r"\b(userdel|passwd\s+-d)\b", "borrar usuarios o contraseñas"),
]
METACARACTERES = re.compile(r"[|;&<>`$(){}*?]")
PELIGRO_MEDIO = re.compile(r"\b(sudo|rm|mv|apt(-get)?\s+(remove|purge)|systemctl\s+(stop|disable)"
                           r"|kill|pkill|chmod|chown|truncate|shred)\b")


@dataclass
class Evaluacion:
    permitido: bool
    peligro: str          # bajo | medio | alto
    motivo: str = ""
    necesita_shell: bool = False


def evaluar(comando: str) -> Evaluacion:
    texto = comando.strip()
    if not texto:
        return Evaluacion(False, "alto", "comando vacío")
    for patron, motivo in BLOQUEADOS:
        if re.search(patron, texto):
            return Evaluacion(False, "alto", f"bloqueado: {motivo}")
    try:
        shlex.split(texto)
    except ValueError:
        return Evaluacion(False, "alto", "comillas sin cerrar")
    shell = bool(METACARACTERES.search(texto))
    peligro = "medio" if PELIGRO_MEDIO.search(texto) or shell else "bajo"
    return Evaluacion(True, peligro, "", shell)


@dataclass
class Paso:
    comando: str
    que_hace: str
    peligro: str
    evaluacion: Evaluacion


EJEMPLO = {"explicacion": "…", "pasos": [
    {"comando": "df -h", "que_hace": "muestra el espacio libre", "peligro": "bajo"}]}


def planificar(
    peticion: str, contexto: str = "", sistema: str | None = None
) -> tuple[str, list[Paso]]:
    respuesta = pedir_json(
        "Traduce la petición a comandos de Ubuntu (bash). Máximo 5 pasos, los más simples y "
        "seguros posibles. Nunca comandos destructivos. Explica cada paso en una frase."
        + (f"\n\nRESULTADO DEL PASO ANTERIOR:\n{contexto[-3000:]}" if contexto else "")
        + f"\n\nPETICIÓN: {peticion}", EJEMPLO, sistema=sistema)
    if not isinstance(respuesta, dict):
        return "", []
    pasos = []
    for p in respuesta.get("pasos") or []:
        if isinstance(p, dict) and isinstance(p.get("comando"), str):
            ev = evaluar(p["comando"])
            orden = ["bajo", "medio", "alto"]
            segun_ia = str(p.get("peligro", "bajo")).lower()
            peligro = max(ev.peligro, segun_ia if segun_ia in orden else "bajo", key=orden.index)
            pasos.append(Paso(p["comando"].strip(), str(p.get("que_hace", "")), peligro, ev))
    return str(respuesta.get("explicacion", "")), pasos[:5]


def ejecutar_paso(ej: Ejecutor, paso: Paso, timeout: float = 120) -> tuple[int, str]:
    if not paso.evaluacion.permitido:
        return 126, paso.evaluacion.motivo
    cmd = ["bash", "-c", paso.comando] if paso.evaluacion.necesita_shell \
        else shlex.split(paso.comando)
    r = ej.run(cmd, check=False, timeout=timeout)
    return r.codigo, (r.salida + r.error).strip()


Preguntar = Callable[[str], str]


def bucle(
    peticion: str,
    *,
    ej: Ejecutor,
    t: tema.Tema,
    preguntar: Preguntar | None = None,
    sistema: str | None = None,
    max_rondas: int = 5,
) -> int:
    """Planifica, enseña, confirma uno a uno y ejecuta. Devuelve los pasos ejecutados."""
    preguntar = preguntar or (lambda texto: typer.prompt(texto, default="n"))
    ejecutados = 0
    contexto = ""
    for ronda in range(max_rondas):
        with t.spinner_ctx("pensando los comandos"):
            explicacion, pasos = planificar(peticion, contexto, sistema)
        if not pasos:
            if ronda == 0:
                t.aviso("La IA no ha propuesto comandos.")
            break
        if explicacion:
            t.consola.print(Text(explicacion, style="texto"))
        tabla = t.tabla("#", "Comando", "Qué hace", "Peligro")
        estilos = {"bajo": "ok", "medio": "aviso", "alto": "error"}
        for i, p in enumerate(pasos, 1):
            peligro = p.peligro if p.evaluacion.permitido else "BLOQUEADO"
            tabla.add_row(str(i), Text(p.comando, style="acento"), p.que_hace,
                          Text(peligro, style=estilos.get(p.peligro, "error")))
        t.consola.print(tabla)
        todos = False
        salida_ronda = []
        for p in pasos:
            if not p.evaluacion.permitido:
                t.error(f"{p.comando}: {p.evaluacion.motivo}")
                continue
            decision = "s" if todos and p.peligro == "bajo" else preguntar(
                f"¿Ejecutar «{p.comando}»? (s/n/todos/editar/fin)").strip().lower()
            if decision.startswith("e"):
                nuevo = preguntar("comando").strip()
                p = Paso(nuevo, p.que_hace, "medio", evaluar(nuevo))
                if not p.evaluacion.permitido:
                    t.error(p.evaluacion.motivo)
                    continue
                decision = "s"
            if decision.startswith("f"):
                return ejecutados
            if decision.startswith("t"):
                todos, decision = True, "s"
            if not decision.startswith("s"):
                continue
            codigo, salida = ejecutar_paso(ej, p)
            ejecutados += 1
            t.consola.print(Text(salida[-4000:] or "(sin salida)", style="apagado"))
            salida_ronda.append(f"$ {p.comando}\n(código {codigo})\n{salida[-1500:]}")
        if not salida_ronda or preguntar("¿Sigo con el siguiente paso? (s/n)") \
                .strip().lower()[:1] != "s":
            break
        contexto = "\n\n".join(salida_ronda)
    return ejecutados


@app.command("haz")
def cmd_haz(peticion: list[str] = typer.Argument(..., help="Lo que quieres hacer.")) -> None:
    """De lenguaje natural a comandos de Ubuntu: te los enseña y solo los ejecuta si confirmas."""
    t = tema.actual()
    n = bucle(" ".join(peticion), ej=Ejecutor(consola=t.consola), t=t)
    t.ok(f"{n} comandos ejecutados.")
