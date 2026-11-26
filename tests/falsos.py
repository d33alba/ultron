"""Dobles de prueba reutilizables por todos los bloques."""

from __future__ import annotations

from typing import Any

from ultron.nucleo.ejecutor import Ejecutor, ErrorEjecucion, Resultado

Respuesta = "Resultado | str | Callable[[list[str]], Resultado | str]"


class EjecutorFalso(Ejecutor):
    """Graba los comandos, simula gsettings con un diccionario y no ejecuta nada real.

    - `programas`: programas que "existen" (None = todos).
    - `respuestas`: {prefijo (tupla o str): Resultado | str | callable(cmd)}; gana el prefijo
      más largo que coincida.
    - `gsettings`: {(esquema, clave): valor}. Si una clave no está, `get` devuelve `defectos`.
    - Los archivos sí se escriben de verdad (los tests usan un HOME temporal).
    """

    def __init__(
        self,
        simular: bool = False,
        programas: set[str] | None = None,
        respuestas: dict[Any, Any] | None = None,
        gsettings: dict[tuple[str, str], str] | None = None,
        fallar: dict[Any, str] | None = None,
    ):
        super().__init__(simular=simular)
        self.programas = programas
        self.respuestas = {self._clave(k): v for k, v in (respuestas or {}).items()}
        self.fallar = {self._clave(k): v for k, v in (fallar or {}).items()}
        self.gsettings: dict[tuple[str, str], str] = dict(gsettings or {})
        self.defectos: dict[tuple[str, str], str] = dict(self.gsettings)

    @staticmethod
    def _clave(k: Any) -> tuple[str, ...]:
        return tuple(k.split()) if isinstance(k, str) else tuple(k)

    def _buscar(self, tabla: dict[tuple[str, ...], Any], cmd: list[str]) -> Any:
        mejor, largo = None, -1
        for prefijo, valor in tabla.items():
            if tuple(cmd[: len(prefijo)]) == prefijo and len(prefijo) > largo:
                mejor, largo = valor, len(prefijo)
        return mejor

    def _responder(self, cmd: list[str]) -> Resultado:
        if cmd[:1] == ["gsettings"] and len(cmd) >= 4:
            accion, esquema, clave = cmd[1], cmd[2], cmd[3]
            if accion == "get":
                valor = self.gsettings.get((esquema, clave))
                return Resultado(0, f"{valor}\n", "") if valor is not None else Resultado(1, "", "")
            if accion == "set" and len(cmd) >= 5:
                self.gsettings[(esquema, clave)] = cmd[4]
                return Resultado(0, "", "")
            if accion == "reset":
                if (esquema, clave) in self.defectos:
                    self.gsettings[(esquema, clave)] = self.defectos[(esquema, clave)]
                else:
                    self.gsettings.pop((esquema, clave), None)
                return Resultado(0, "", "")
        if cmd[:2] == ["gsettings", "list-keys"]:
            return Resultado(0, "", "")
        valor = self._buscar(self.respuestas, cmd)
        if callable(valor):
            valor = valor(cmd)
        if isinstance(valor, Resultado):
            return valor
        if isinstance(valor, str):
            return Resultado(0, valor, "")
        return Resultado(0, "", "")

    def run(self, cmd, *, sudo=False, check=True, entrada=None, timeout=60, fondo=False):
        cmd = [str(c) for c in cmd]
        if sudo:
            cmd = ["sudo"] + cmd
        self._registrar(cmd)
        if self.simular:
            return Resultado(0, "", "")
        mensaje = self._buscar(self.fallar, cmd)
        if mensaje is not None:
            raise ErrorEjecucion(mensaje)
        res = self._responder(cmd[1:] if sudo else cmd)
        if check and res.codigo != 0:
            raise ErrorEjecucion(f"falló: {' '.join(cmd)}")
        return res

    def leer(self, cmd, *, timeout=15):
        return self._responder([str(c) for c in cmd])

    def existe(self, programa: str) -> bool:
        return self.programas is None or programa in self.programas

    def comandos(self, prefijo: str | None = None) -> list[str]:
        textos = [" ".join(c) for c in self.historial]
        return [t for t in textos if prefijo is None or t.startswith(prefijo)]
