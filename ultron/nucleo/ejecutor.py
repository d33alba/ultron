"""Único punto de entrada para los comandos y cambios del sistema.

En modo simulado no cambia nada: registra y pinta. Las lecturas sí se ejecutan.
"""

from __future__ import annotations

import os
import shlex
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any


class ErrorEjecucion(Exception):
    """Un comando del sistema ha fallado."""


@dataclass
class Resultado:
    codigo: int
    salida: str
    error: str

    @property
    def ok(self) -> bool:
        return self.codigo == 0


def _texto(cmd: list[str]) -> str:
    try:
        return shlex.join(cmd)
    except TypeError:
        return " ".join(map(str, cmd))


class Ejecutor:
    def __init__(self, simular: bool = False, consola: Any = None, suponer: bool = False):
        self.simular = simular
        self.consola = consola
        # suponer=True (solo al simular): se actúa como si todos los programas existieran,
        # para ver en Windows o en CI todo lo que haría Ultron en un Ubuntu con GNOME.
        self.suponer = suponer and simular
        self.historial: list[list[str]] = []

    # --- registro -------------------------------------------------------------
    def _registrar(self, cmd: list[str]) -> None:
        self.historial.append(list(cmd))
        if self.simular and self.consola is not None:
            legible = " ".join(f'"{c}"' if " " in c else c for c in map(str, cmd))
            self.consola.print(
                f"[apagado]  simular ▸[/] {legible}", markup=False, highlight=False
            )

    @staticmethod
    def _prefijo_sudo() -> list[str]:
        if os.environ.get("ULTRON_SUDO"):
            return shlex.split(os.environ["ULTRON_SUDO"])
        return ["sudo"] if sys.stdin is not None and sys.stdin.isatty() else ["pkexec"]

    # --- comandos -------------------------------------------------------------
    def run(
        self,
        cmd: list[str],
        *,
        sudo: bool = False,
        check: bool = True,
        entrada: str | None = None,
        timeout: float | None = 60,
        fondo: bool = False,
        directorio: Path | None = None,
        registro: Path | None = None,
    ) -> Resultado:
        cmd = [str(c) for c in cmd]
        if sudo:
            cmd = self._prefijo_sudo() + cmd
        self._registrar(cmd)
        if self.simular:
            return Resultado(0, "", "")
        opciones = {}
        if directorio is not None:
            opciones["directorio"] = directorio
        if registro is not None:
            opciones["registro"] = registro
        return self._ejecutar(cmd, check=check, entrada=entrada, timeout=timeout, fondo=fondo,
                              **opciones)

    def leer(self, cmd: list[str], *, timeout: float | None = 15) -> Resultado:
        """Ejecuta un comando de solo lectura, también al simular. Nunca lanza."""
        if self.suponer and shutil.which(str(cmd[0])) is None:
            return Resultado(0, "", "")
        try:
            return self._ejecutar([str(c) for c in cmd], check=False, timeout=timeout)
        except ErrorEjecucion as e:
            return Resultado(127, "", str(e))

    def _ejecutar(
        self,
        cmd: list[str],
        *,
        check: bool,
        entrada: str | None = None,
        timeout: float | None = 60,
        fondo: bool = False,
        directorio: Path | None = None,
        registro: Path | None = None,
    ) -> Resultado:
        try:
            if fondo:
                from contextlib import nullcontext

                salida = registro.open("ab") if registro is not None else nullcontext(
                    subprocess.DEVNULL
                )
                with salida as flujo:
                    proc = subprocess.Popen(
                        cmd, stdout=flujo, stderr=flujo, stdin=subprocess.DEVNULL,
                        start_new_session=True, cwd=directorio,
                    )
                return Resultado(0, str(proc.pid), "")
            p = subprocess.run(
                cmd, input=entrada, capture_output=True, text=True, timeout=timeout,
                cwd=directorio,
            )
        except FileNotFoundError as e:
            raise ErrorEjecucion(f"No encuentro el programa «{cmd[0]}». ¿Está instalado?") from e
        except subprocess.TimeoutExpired as e:
            raise ErrorEjecucion(f"«{_texto(cmd)}» tardó más de {timeout} s.") from e
        res = Resultado(p.returncode, p.stdout or "", p.stderr or "")
        if check and p.returncode != 0:
            detalle = (res.error or res.salida).strip()[:300]
            raise ErrorEjecucion(f"«{_texto(cmd)}» falló (código {p.returncode}): {detalle}")
        return res

    def existe(self, programa: str) -> bool:
        return self.suponer or shutil.which(programa) is not None

    # --- gsettings ------------------------------------------------------------
    def gsettings_get(self, esquema: str, clave: str) -> str | None:
        if self.suponer and shutil.which("gsettings") is None:
            return "''"
        if not self.existe("gsettings"):
            return None
        r = self.leer(["gsettings", "get", esquema, clave])
        return r.salida.strip() if r.codigo == 0 else None

    def gsettings_set(self, esquema: str, clave: str, valor: str) -> None:
        self.run(["gsettings", "set", esquema, clave, valor])

    def gsettings_reset(self, esquema: str, clave: str) -> None:
        self.run(["gsettings", "reset", esquema, clave])

    def gsettings_existe(self, esquema: str) -> bool:
        if not self.existe("gsettings"):
            return False
        r = self.leer(["gsettings", "list-keys", esquema])
        return r.codigo == 0

    # --- archivos ---------------------------------------------------------------
    def escribir(
        self,
        ruta: Path,
        contenido: str | bytes,
        *,
        sudo: bool = False,
        modo: int | None = None,
    ) -> None:
        ruta = Path(ruta)
        if sudo:
            if isinstance(contenido, bytes):
                contenido = contenido.decode("utf-8")
            self.run(["tee", str(ruta)], sudo=True, entrada=contenido)
            if modo is not None:
                self.run(["chmod", f"{modo:o}", str(ruta)], sudo=True)
            return
        self._registrar(["#escribir", str(ruta)])
        if self.simular:
            return
        ruta.parent.mkdir(parents=True, exist_ok=True)
        temporal = ruta.with_name(ruta.name + ".ultron-tmp")
        if isinstance(contenido, bytes):
            temporal.write_bytes(contenido)
        else:
            temporal.write_text(contenido, encoding="utf-8", newline="\n")
        if modo is not None:
            os.chmod(temporal, modo)
        os.replace(temporal, ruta)

    def borrar(self, ruta: Path, *, sudo: bool = False) -> None:
        ruta = Path(ruta)
        if sudo:
            self.run(["rm", "-rf", str(ruta)], sudo=True)
            return
        self._registrar(["#borrar", str(ruta)])
        if self.simular:
            return
        if ruta.is_dir() and not ruta.is_symlink():
            shutil.rmtree(ruta, ignore_errors=True)
        elif ruta.exists() or ruta.is_symlink():
            ruta.unlink()

    def copiar(self, origen: Path, destino: Path, *, sudo: bool = False) -> None:
        origen, destino = Path(origen), Path(destino)
        if sudo:
            self.run(["cp", "-r", str(origen), str(destino)], sudo=True)
            return
        self._registrar(["#copiar", str(origen), str(destino)])
        if self.simular:
            return
        destino.parent.mkdir(parents=True, exist_ok=True)
        if origen.is_dir():
            shutil.copytree(origen, destino, dirs_exist_ok=True)
        else:
            shutil.copy2(origen, destino)
