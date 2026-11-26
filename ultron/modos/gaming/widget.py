"""Valores dinámicos para el HUD de Conky."""

import sys

from ultron.modos.gaming.funciones.hud import gpu
from ultron.nucleo import rutas, xp
from ultron.nucleo.ejecutor import Ejecutor
from ultron.ui import tema


def main() -> None:
    consola = tema.consola()
    if len(sys.argv) > 1 and sys.argv[1] == "gpu":
        valor = gpu(Ejecutor())
        consola.print("N/D" if valor is None else f"{valor:.0f}", markup=False)
    else:
        consola.print(f"PLAYER: {rutas.home().name}  LVL {xp.nivel(xp.leer()['xp'])}",
                      markup=False, highlight=False)


if __name__ == "__main__":
    main()

