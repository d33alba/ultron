"""Capas sistema (notificaciones, energía, webs bloqueadas, CPU) y widgets (Conky)."""

from __future__ import annotations

import sys
from pathlib import Path

from ultron.capas import comun as C
from ultron.capas.base import Capa, registrar_capa
from ultron.nucleo import estado, hosts, rutas
from ultron.nucleo.ejecutor import Ejecutor
from ultron.ui.tema import cargar_tema

NOTIF = "org.gnome.desktop.notifications"
SESION = "org.gnome.desktop.session"
PANTALLA = "org.gnome.desktop.screensaver"
INTERFAZ = "org.gnome.desktop.interface"
COLOR = "org.gnome.settings-daemon.plugins.color"
PRIVACIDAD = "org.gnome.desktop.privacy"
BUSQUEDA = "org.gnome.desktop.search-providers"
UBICACION = "org.gnome.system.location"
ATAJOS = "/org/gnome/settings-daemon/plugins/media-keys/custom-keybindings"
ATAJO = ATAJOS + "/ultron-clip/"
CLAVES_ATAJO = [ATAJOS, *(ATAJO + k for k in ("name", "command", "binding"))]


def _atajo(ej: Ejecutor) -> None:
    import shlex

    lista = C.leer_lista(C.dconf_leer(ej, ATAJOS))
    if ATAJO not in lista:
        lista.append(ATAJO)
    comando = shlex.join([sys.executable, "-m", "ultron", "clip", "guardar"])
    for clave, valor in {"name": "Guardar clip de Ultron", "command": comando,
                         "binding": "<Super><Alt>r"}.items():
        C.dconf_escribir(ej, ATAJO + clave, C.gv_str(valor))
    C.dconf_escribir(ej, ATAJOS, C.gv_lista(lista))
CLAVES = [
    (NOTIF, "show-banners"), (SESION, "idle-delay"), (PANTALLA, "lock-enabled"),
    (INTERFAZ, "text-scaling-factor"), (COLOR, "night-light-enabled"),
    (PRIVACIDAD, "remember-recent-files"), (PRIVACIDAD, "remove-old-temp-files"),
    (PRIVACIDAD, "remove-old-trash-files"), (PRIVACIDAD, "old-files-age"),
    (PRIVACIDAD, "report-technical-problems"), (PRIVACIDAD, "send-software-usage-stats"),
    (BUSQUEDA, "disable-external"), (UBICACION, "enabled"),
]


@registrar_capa
class CapaSistema(Capa):
    nombre = "sistema"
    orden = 70
    descripcion = "Notificaciones, suspensión, luz nocturna, privacidad, webs bloqueadas, CPU"

    def capturar(self, cfg: dict) -> dict:
        perfil = None
        if self.ej.existe("powerprofilesctl"):
            r = self.ej.leer(["powerprofilesctl", "get"])
            perfil = r.salida.strip() or None
        return {"claves": C.capturar_claves(self.ej, CLAVES), "perfil": perfil,
                "hosts": bool(cfg.get("bloquear")),
                "atajo": {k: C.dconf_leer(self.ej, k) for k in CLAVES_ATAJO}
                if cfg.get("atajo_clip") and self.ej.existe("dconf") else {}}

    def aplicar(self, cfg: dict) -> None:
        previo = C.capturar_claves(self.ej, CLAVES)
        fijar = lambda esq, k, v: C.fijar_si_existe(self.ej, previo, esq, k, v)  # noqa: E731
        if "notificaciones" in cfg:
            fijar(NOTIF, "show-banners", C.gv_bool(cfg["notificaciones"]))
        if "suspension_min" in cfg:
            fijar(SESION, "idle-delay", f"uint32 {int(cfg['suspension_min']) * 60}")
        if "bloqueo_pantalla" in cfg:
            fijar(PANTALLA, "lock-enabled", C.gv_bool(cfg["bloqueo_pantalla"]))
        if "escala_texto" in cfg:
            fijar(INTERFAZ, "text-scaling-factor", str(float(cfg["escala_texto"])))
        if "luz_nocturna" in cfg:
            fijar(COLOR, "night-light-enabled", C.gv_bool(cfg["luz_nocturna"]))
        priv = cfg.get("privacidad")
        if priv:
            fijar(PRIVACIDAD, "remember-recent-files", "false")
            fijar(PRIVACIDAD, "remove-old-temp-files", "true")
            fijar(PRIVACIDAD, "remove-old-trash-files", "true")
            fijar(PRIVACIDAD, "old-files-age", "uint32 1")
            fijar(PRIVACIDAD, "report-technical-problems", "false")
            fijar(PRIVACIDAD, "send-software-usage-stats", "false")
            fijar(BUSQUEDA, "disable-external", "true")
            fijar(UBICACION, "enabled", "false")
        if cfg.get("atajo_clip") and self.ej.existe("dconf"):
            _atajo(self.ej)
        if cfg.get("bloquear"):
            hosts.bloquear(self.ej, list(cfg["bloquear"]), etiqueta=f"modo-{self.ctx.modo.id}")
        if cfg.get("perfil_energia") and self.ej.existe("powerprofilesctl"):
            self.ej.run(["powerprofilesctl", "set", cfg["perfil_energia"]], check=False)

    def restaurar(self, previo: dict) -> None:
        C.restaurar_claves(self.ej, previo.get("claves", {}))
        for clave, valor in previo.get("atajo", {}).items():
            C.dconf_restaurar(self.ej, clave, valor)
        if previo.get("hosts"):
            hosts.desbloquear(self.ej, etiqueta=f"modo-{self.ctx.modo.id}")
        if previo.get("perfil") and self.ej.existe("powerprofilesctl"):
            self.ej.run(["powerprofilesctl", "set", previo["perfil"]], check=False)


# --- widgets ---------------------------------------------------------------------

CONKY_DEFECTO = """conky.config = {
  alignment = 'top_right', gap_x = 40, gap_y = 70, minimum_width = 300,
  own_window = true, own_window_type = 'desktop', own_window_transparent = true,
  own_window_argb_visual = true,
  own_window_hints = 'undecorated,below,sticky,skip_taskbar,skip_pager',
  double_buffer = true, update_interval = 1, use_xft = true,
  font = '@@fuente@@:size=11', default_color = '@@texto@@',
  color1 = '@@primario@@', color2 = '@@acento@@', color3 = '@@apagado@@',
  draw_shades = false, draw_outline = false, draw_borders = false,
};
conky.text = [[
${color1}${font @@fuente@@:bold:size=30}${time %H:%M}${font}${color}
${color3}${time %A %d %B}${color}
${color1}@@marca@@ @@nombre@@${color} ${color3}${hr 1}${color}
${color2}CPU${color} ${cpu}% ${alignr}${color1}${cpubar 8,150}${color}
${color2}RAM${color} ${memperc}% ${alignr}${color1}${membar 8,150}${color}
${color2}DISCO${color} ${fs_used_perc /}% ${alignr}${color1}${fs_bar 8,150 /}${color}
${color2}RED${color} ↓ ${downspeedf @@red@@} KiB/s ${alignr}↑ ${upspeedf @@red@@} KiB/s
${color3}UPTIME ${uptime_short}${color}
]];
"""


def renderizar_conky(plantilla: str, valores: dict[str, str]) -> str:
    for clave, valor in valores.items():
        plantilla = plantilla.replace(f"@@{clave}@@", valor)
    return plantilla


def _interfaz_red() -> str:
    try:
        for linea in Path("/proc/net/route").read_text().splitlines()[1:]:
            partes = linea.split()
            if len(partes) > 1 and partes[1] == "00000000":
                return partes[0]
    except OSError:
        pass
    return "eth0"


@registrar_capa
class CapaWidgets(Capa):
    nombre = "widgets"
    orden = 60
    descripcion = "Widgets de escritorio con Conky"

    def disponible(self) -> tuple[bool, str]:
        if self.ej.existe("conky"):
            return True, ""
        return False, "falta conky (sudo apt install conky-all)"

    def _rutas(self) -> tuple[Path, Path]:
        conf = rutas.config() / "conky" / f"{self.ctx.modo.id}.conf"
        auto = rutas.xdg_config_raiz() / "autostart" / "ultron-widgets.desktop"
        return conf, auto

    def capturar(self, cfg: dict) -> dict:
        return {"auto_existia": self._rutas()[1].exists()}

    def aplicar(self, cfg: dict) -> None:
        tema = cargar_tema(self.ctx.modo.id)
        p = tema.paleta
        fuente_plantilla = self.ctx.recurso(cfg.get("plantilla", "tema/conky.conf"))
        plantilla = (fuente_plantilla.read_text(encoding="utf-8")
                     if fuente_plantilla.exists() else CONKY_DEFECTO)
        valores = {k: v for k, v in p.items()}
        valores.update({
            "fuente": cfg.get("fuente", "JetBrains Mono"), "marca": tema.glifo("marca"),
            "nombre": self.ctx.modo.nombre, "red": _interfaz_red(),
            "usuario": rutas.home().name,
        })
        if self.ctx.modo.id == "netanyahu":
            import shlex

            comando = shlex.join([sys.executable, "-m", "ultron.modos.netanyahu.radar_status"])
            valores["radar_publica"] = f"{comando} publica"
            valores["radar_local"] = f"{comando} local"
        if self.ctx.modo.id == "gaming":
            import shlex

            comando = shlex.join([sys.executable, "-m", "ultron.modos.gaming.widget"])
            valores["hud"] = comando
            if self.ej.existe("conky") and "cairo" in self.ej.leer(["conky", "-v"]).salida.lower():
                lua = self.ctx.recurso("tema/anillos.lua")
                if lua.is_file():
                    destino_lua = self._rutas()[0].with_suffix(".lua")
                    self.ej.escribir(destino_lua, renderizar_conky(
                        lua.read_text(encoding="utf-8"), valores))
                    plantilla = plantilla.replace("conky.config = {", (
                        f"conky.config = {{\n  lua_load = {str(destino_lua)!r}, "
                        "lua_draw_hook_pre = 'anillos',"
                    ))
                    plantilla = plantilla.replace("@@anillos@@", "\n\n\n\n")
            plantilla = plantilla.replace("@@anillos@@", "")
        conf, auto = self._rutas()
        self.ej.escribir(conf, renderizar_conky(plantilla, valores))
        res = self.ej.run(["conky", "-c", str(conf)], check=False, fondo=True)
        if not self.ej.simular and res.salida.isdigit():
            estado.actualizar(conky_pid=int(res.salida))
        self.ej.escribir(auto, (
            "[Desktop Entry]\nType=Application\nName=Ultron widgets\n"
            f"Exec=sh -c 'sleep 5; conky -c \"{conf}\"'\nX-GNOME-Autostart-enabled=true\n"
            "NoDisplay=true\n"))

    def restaurar(self, previo: dict) -> None:
        C.matar(estado.obtener("conky_pid"))
        if not self.ej.simular:
            estado.actualizar(conky_pid=None)
        conf, auto = self._rutas()
        if not previo.get("auto_existia"):
            self.ej.borrar(auto)


def python_actual() -> str:
    return sys.executable
