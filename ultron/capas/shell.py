"""Capa shell: prompt del modo, alias, variables y bienvenida en bash."""

from __future__ import annotations

import re
import shlex
import sys
from pathlib import Path

from ultron.capas.base import Capa, registrar_capa
from ultron.nucleo import rutas
from ultron.ui.tema import Tema, cargar_tema

INICIO = "# >>> ultron >>>"
FIN = "# <<< ultron <<<"
_TOKEN_COLOR = re.compile(r"\{c:([a-z_]+)\}")


def ruta_sh() -> Path:
    return rutas.config() / "shell" / "ultron.sh"


def ruta_bashrc() -> Path:
    return rutas.home() / ".bashrc"


def bloque_bashrc() -> str:
    return (
        f"{INICIO}\n"
        "[ -f ~/.config/ultron/shell/ultron.sh ] && . ~/.config/ultron/shell/ultron.sh\n"
        f"{FIN}\n"
    )


def _ansi(color: str) -> str:
    color = color.lstrip("#")
    if len(color) != 6:
        return ""
    r, g, b = (int(color[i : i + 2], 16) for i in (0, 2, 4))
    return f"\\[\\e[38;2;{r};{g};{b}m\\]"


def renderizar_prompt(plantilla: str, tema: Tema, nombre_modo: str) -> str:
    """Convierte la plantilla del modo en un PS1 de bash con colores truecolor."""
    ps1 = _TOKEN_COLOR.sub(lambda m: _ansi(tema.paleta.get(m.group(1), "")), plantilla)
    reemplazos = {
        "{reset}": "\\[\\e[0m\\]",
        "{usuario}": "\\u",
        "{host}": "\\h",
        "{dir}": "\\w",
        "{modo}": nombre_modo,
        "{extra}": "$(__ultron_extra)",
    }
    for token, valor in reemplazos.items():
        ps1 = ps1.replace(token, valor)
    return ps1


def _comillas(texto: str) -> str:
    return "'" + texto.replace("'", "'\\''") + "'"


def generar_script(cfg: dict, tema: Tema, nombre_modo: str, python: str | None = None) -> str:
    python = python or sys.executable
    plantilla = cfg.get("prompt") or tema.prompt or "{usuario}@{host} {dir} ❯ "
    lineas = [
        f"# Generado por Ultron (modo {nombre_modo}). No editar: se regenera al cambiar de modo.",
        f"export ULTRON_MODO={shlex.quote(tema.id)}",
        f"__ultron_extra() {{ {shlex.quote(python)} -I -m ultron.prompt_extra 2>/dev/null; }}",
        f"PS1={_comillas(renderizar_prompt(plantilla, tema, nombre_modo))}",
    ]
    for nombre, valor in (cfg.get("variables") or {}).items():
        lineas.append(f"export {nombre}={shlex.quote(str(valor))}")
    for nombre, valor in (cfg.get("alias") or {}).items():
        lineas.append(f"alias {nombre}={shlex.quote(str(valor))}")
    lineas.append("alias uerr='ultron error'")
    if cfg.get("historial") is False:
        lineas += ["export HISTFILE=/dev/null", "unset HISTFILE"]
    lineas += [
        "__ultron_capturar() { local c=$?; "
        "printf '%s\\t%s\\n' \"$c\" \"$(HISTTIMEFORMAT= history 1 | sed 's/^ *[0-9]* *//')\" "
        "2>/dev/null > \"${XDG_STATE_HOME:-$HOME/.local/state}/ultron/ultimo_cmd\"; return $c; }",
        'case ";$PROMPT_COMMAND;" in *";__ultron_capturar;"*) ;; '
        '*) PROMPT_COMMAND="__ultron_capturar${PROMPT_COMMAND:+;$PROMPT_COMMAND}";; esac',
    ]
    if cfg.get("bienvenida", True):
        lineas.append(
            'if [ -z "$ULTRON_BIENVENIDA" ] && [ -t 1 ]; then export ULTRON_BIENVENIDA=1; '
            "command -v ultron >/dev/null && ultron bienvenida; fi"
        )
    return "\n".join(lineas) + "\n"


def quitar_bloque(texto: str) -> str:
    patron = re.compile(rf"\n?{re.escape(INICIO)}.*?{re.escape(FIN)}\n?", re.S)
    return patron.sub("\n", texto).rstrip("\n") + ("\n" if texto.strip() else "")


@registrar_capa
class CapaShell(Capa):
    nombre = "shell"
    orden = 5
    descripcion = "Prompt, alias y variables de bash"

    def capturar(self, cfg: dict) -> dict:
        bashrc = ruta_bashrc()
        contenido = bashrc.read_text(encoding="utf-8") if bashrc.exists() else ""
        sh = ruta_sh()
        return {
            "bloque_existia": INICIO in contenido,
            "separador": bool(contenido) and not contenido.endswith("\n"),
            "sh_previo": sh.read_text(encoding="utf-8") if sh.exists() else None,
        }

    def aplicar(self, cfg: dict) -> None:
        tema = cargar_tema(self.ctx.modo.id)
        self.ej.escribir(ruta_sh(), generar_script(cfg, tema, self.ctx.modo.nombre))
        bashrc = ruta_bashrc()
        contenido = bashrc.read_text(encoding="utf-8") if bashrc.exists() else ""
        if INICIO not in contenido:
            separador = "" if not contenido or contenido.endswith("\n") else "\n"
            self.ej.escribir(bashrc, contenido + separador + bloque_bashrc())

    def restaurar(self, previo: dict) -> None:
        if previo.get("sh_previo") is not None:
            self.ej.escribir(ruta_sh(), previo["sh_previo"])
        else:
            self.ej.borrar(ruta_sh())
        if not previo.get("bloque_existia"):
            bashrc = ruta_bashrc()
            if bashrc.exists():
                contenido = bashrc.read_text(encoding="utf-8")
                if bloque_bashrc() in contenido:
                    nuevo = contenido.replace(bloque_bashrc(), "", 1)
                    if previo.get("separador") and nuevo.endswith("\n"):
                        nuevo = nuevo[:-1]
                    self.ej.escribir(bashrc, nuevo)
                elif INICIO in contenido:
                    self.ej.escribir(bashrc, quitar_bloque(contenido))
