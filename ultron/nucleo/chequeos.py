"""Comprobaciones básicas del sistema para doctor."""

from __future__ import annotations

from ultron.nucleo import registro
from ultron.nucleo.doctor import Chequeo, OpcionesDoctor, comprobacion
from ultron.nucleo.ejecutor import Ejecutor
from ultron.nucleo.entorno import detectar


@comprobacion("Sistema operativo")
def _so(ej: Ejecutor, _o: OpcionesDoctor) -> Chequeo:
    ent = detectar(ej)
    if ent.es_ubuntu:
        return Chequeo("Sistema operativo", "ok", f"Ubuntu {ent.version}")
    if ent.es_linux:
        return Chequeo(
            "Sistema operativo", "aviso", f"{ent.distro} {ent.version}",
            "Ultron está pensado para Ubuntu 24.04+; algunas capas pueden no funcionar.",
        )
    return Chequeo(
        "Sistema operativo", "aviso", f"{ent.distro} {ent.version}",
        "Las capas solo se aplican en Ubuntu. Aquí puedes usar --simular y las funciones.",
    )


@comprobacion("GNOME")
def _gnome(ej: Ejecutor, _o: OpcionesDoctor) -> Chequeo:
    ent = detectar(ej)
    if ent.gnome_mayor is None:
        return Chequeo("GNOME", "error", "No se detecta GNOME Shell",
                       "Ultron transforma el escritorio GNOME (Ubuntu 24.04 lo trae).")
    if ent.gnome_mayor < 45:
        return Chequeo("GNOME", "aviso", f"GNOME {ent.gnome}",
                       "Las extensiones necesitan GNOME 45 o superior.")
    return Chequeo("GNOME", "ok", f"GNOME {ent.gnome} · sesión {ent.sesion or '¿?'}")


@comprobacion("Herramientas básicas")
def _herramientas(ej: Ejecutor, _o: OpcionesDoctor) -> Chequeo:
    faltan = [p for p in ("gsettings", "dconf", "gnome-extensions") if not ej.existe(p)]
    if not faltan:
        return Chequeo("Herramientas básicas", "ok", "gsettings, dconf, gnome-extensions")
    return Chequeo("Herramientas básicas", "error", "Faltan: " + ", ".join(faltan),
                   "sudo apt install dconf-cli gnome-shell-extensions")


@comprobacion("Recursos de los modos", grupo="modos")
def _recursos(_ej: Ejecutor, _o: OpcionesDoctor) -> list[Chequeo]:
    resultados = []
    for modo in registro.listar():
        faltan = [r for r in modo.recursos_opcionales if not modo.tiene_recurso(r.ruta)]
        if not faltan:
            resultados.append(Chequeo(f"Recursos · {modo.nombre}", "ok", "completos"))
            continue
        detalle = "; ".join(f"{r.ruta} ({r.descripcion})" for r in faltan)
        destino = modo.dir_usuario() / "tema"
        resultados.append(
            Chequeo(
                f"Recursos · {modo.nombre}", "aviso", f"Faltan: {detalle}",
                f"Ponlos en {destino} o usa: ultron tema importar <carpeta> --modo {modo.id}",
            )
        )
    return resultados
