from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import httpx
import pytest
from falsos import EjecutorFalso
from PIL import Image

from ultron.capas import (
    arranque,
    comun,
    cursor,
    escritorio,
    estilos,
    extensiones,
    iconos_gen,
    sistema,
    sonido,
    terminal,
    xcursor,
)
from ultron.capas.base import Contexto
from ultron.nucleo import estado, hosts, motor, panel, registro

GS = {
    ("org.gnome.desktop.background", "picture-uri"): "'file:///fondo-original.png'",
    ("org.gnome.desktop.background", "picture-uri-dark"): "'file:///fondo-original.png'",
    ("org.gnome.desktop.background", "picture-options"): "'zoom'",
    ("org.gnome.desktop.background", "primary-color"): "'#000000'",
    ("org.gnome.desktop.screensaver", "picture-uri"): "'file:///bloqueo.png'",
    ("org.gnome.desktop.screensaver", "picture-options"): "'zoom'",
    ("org.gnome.desktop.screensaver", "lock-enabled"): "true",
    ("org.gnome.desktop.interface", "color-scheme"): "'default'",
    ("org.gnome.desktop.interface", "gtk-theme"): "'Yaru'",
    ("org.gnome.desktop.interface", "accent-color"): "'orange'",
    ("org.gnome.desktop.interface", "font-name"): "'Ubuntu Sans 11'",
    ("org.gnome.desktop.interface", "document-font-name"): "'Sans 11'",
    ("org.gnome.desktop.interface", "monospace-font-name"): "'Ubuntu Mono 13'",
    ("org.gnome.desktop.interface", "enable-animations"): "true",
    ("org.gnome.desktop.interface", "clock-show-seconds"): "false",
    ("org.gnome.desktop.interface", "icon-theme"): "'Yaru'",
    ("org.gnome.desktop.interface", "cursor-theme"): "'Yaru'",
    ("org.gnome.desktop.interface", "cursor-size"): "24",
    ("org.gnome.desktop.interface", "text-scaling-factor"): "1.0",
    ("org.gnome.shell.extensions.dash-to-dock", "dock-position"): "'LEFT'",
    ("org.gnome.shell.extensions.dash-to-dock", "dash-max-icon-size"): "48",
    ("org.gnome.shell.extensions.dash-to-dock", "autohide"): "true",
    ("org.gnome.shell.extensions.dash-to-dock", "background-color"): "'#ffffff'",
    ("org.gnome.desktop.sound", "theme-name"): "'Yaru'",
    ("org.gnome.desktop.sound", "event-sounds"): "true",
    ("org.gnome.desktop.notifications", "show-banners"): "true",
    ("org.gnome.desktop.session", "idle-delay"): "uint32 300",
    ("org.gnome.settings-daemon.plugins.color", "night-light-enabled"): "false",
    ("org.gnome.desktop.privacy", "remember-recent-files"): "true",
    ("org.gnome.shell", "enabled-extensions"): "['ubuntu-dock@ubuntu.com']",
    ("org.gnome.shell", "disabled-extensions"): "@as []",
}


@pytest.fixture
def ejg():
    return EjecutorFalso(gsettings=dict(GS))


def _ctx(id_modo: str) -> Contexto:
    m = registro.obtener(id_modo)
    return Contexto(modo=m, dir_modo=m.dir)


def _ciclo(capa_cls, ej, id_modo, cfg=None):
    """capturar → aplicar → restaurar. Devuelve (gsettings tras aplicar, tras restaurar)."""
    cfg = registro.obtener(id_modo).capas.get(capa_cls.nombre, {}) if cfg is None else cfg
    antes_gs, antes_dc = dict(ej.gsettings), dict(ej.dconf)
    capa = capa_cls(ej, _ctx(id_modo))
    previo = json.loads(json.dumps(capa.capturar(cfg)))  # debe ser serializable
    capa.aplicar(cfg)
    aplicado = dict(ej.gsettings)
    capa.restaurar(previo)
    assert ej.gsettings == antes_gs
    assert ej.dconf == antes_dc
    return aplicado


# --- escritorio / estilos ---------------------------------------------------------


def test_escritorio_aplica_y_restaura(ejg, tmp_home):
    css_previo = tmp_home / ".config" / "gtk-4.0" / "gtk.css"
    css_previo.parent.mkdir(parents=True)
    css_previo.write_text("/* mío */", encoding="utf-8")
    aplicado = _ciclo(escritorio.CapaEscritorio, ejg, "netanyahu")
    assert aplicado[("org.gnome.desktop.interface", "gtk-theme")] == "'Ultron-netanyahu'"
    assert aplicado[("org.gnome.desktop.interface", "color-scheme")] == "'prefer-dark'"
    assert aplicado[("org.gnome.shell.extensions.dash-to-dock", "dock-position")] == "'BOTTOM'"
    assert "file://" in aplicado[("org.gnome.desktop.background", "picture-uri")]
    assert css_previo.read_text(encoding="utf-8") == "/* mío */"
    tema = escritorio.dir_tema("netanyahu")
    assert (tema / "gnome-shell" / "gnome-shell.css").exists()
    assert (tema / "gtk-3.0" / "gtk.css").exists()


def test_escritorio_fondo_de_respaldo(ejg):
    escritorio.CapaEscritorio(ejg, _ctx("gaming")).aplicar({"fondo": "tema/no-existe.png"})
    uri = ejg.gsettings[("org.gnome.desktop.background", "picture-uri")]
    ruta = Path(uri.strip("'").replace("file:///", "").replace("file://", ""))
    if not ruta.is_absolute():
        ruta = Path("/") / ruta
    assert ruta.exists() and Image.open(ruta).size == (1920, 1080)


def test_claves_inexistentes_no_se_tocan(tmp_home):
    ej = EjecutorFalso(gsettings={})  # GNOME sin ninguna clave conocida
    escritorio.CapaEscritorio(ej, _ctx("focus")).aplicar({"esquema": "oscuro"})
    assert not any(c.startswith("gsettings set") for c in ej.comandos())


def test_css_generados_usan_la_paleta():
    p = {"fondo": "#0A1A3F", "primario": "#2F6BFF", "bandera": "#0038B8", "texto": "#ffffff",
         "acento": "#6EA8FE"}
    assert "#0038B8" in estilos.css_gtk4(p)
    assert "@define-color accent_bg_color #0038B8" in estilos.css_gtk4(p)
    assert "gtk-contained-dark.css" in estilos.css_gtk3(p)
    shell = estilos.css_shell(p, brillo=True)
    assert "#panel" in shell and "box-shadow" in shell


# --- terminal -------------------------------------------------------------------------


def test_terminal_perfil_dconf(tmp_home):
    ej = EjecutorFalso(programas={"dconf", "gnome-terminal"})
    base = terminal.BASE_GT
    ej.dconf[base + "list"] = "['viejo']"
    ej.dconf[base + "default"] = "'viejo'"
    capa = terminal.CapaTerminal(ej, _ctx("gaming"))
    previo = capa.capturar({})
    capa.aplicar({"transparencia": 12})
    uuid = comun.uuid_modo("gaming")
    assert ej.dconf[base + "default"] == f"'{uuid}'"
    assert comun.leer_lista(ej.dconf[base + "list"]) == ["viejo", uuid]
    paleta = comun.leer_lista(ej.dconf[f"{base}:{uuid}/palette"])
    assert len(paleta) == 16 and paleta[4].upper() == "#FF00E6"
    assert ej.dconf[f"{base}:{uuid}/background-transparency-percent"] == "12"
    capa.restaurar(previo)
    assert ej.dconf == {base + "list": "['viejo']", base + "default": "'viejo'"}


def test_paleta_terminal_16():
    assert len(comun.paleta_terminal({"fondo": "#000000", "primario": "#ff0000"})) == 16


# --- iconos ------------------------------------------------------------------------------


@pytest.fixture
def tema_base(tmp_path):
    base = tmp_path / "Yaru"
    (base / "48x48" / "apps").mkdir(parents=True)
    (base / "48x48" / "places").mkdir(parents=True)
    (base / "scalable" / "mimetypes").mkdir(parents=True)
    (base / "index.theme").write_text(
        "[Icon Theme]\nName=Yaru\nInherits=hicolor\nDirectories=48x48/apps\n", encoding="utf-8")
    Image.new("RGBA", (48, 48), (233, 84, 32, 255)).save(base / "48x48" / "apps" / "firefox.png")
    Image.new("RGBA", (48, 48), (233, 84, 32, 255)).save(base / "48x48" / "places" / "folder.png")
    (base / "scalable" / "mimetypes" / "text-x-generic.svg").write_text(
        '<svg viewBox="0 0 16 16"><path fill="#e95420" d="M0 0h16v16H0z"/>'
        '<path fill="#ffffff" d="M1 1h2v2H1z"/></svg>', encoding="utf-8")
    return base


def _emblema(tmp_path) -> Path:
    ruta = tmp_path / "emblema.png"
    Image.new("RGBA", (64, 64), (255, 255, 255, 255)).save(ruta)
    return ruta


def test_generar_iconos(tmp_path, tema_base):
    propios = tmp_path / "propios"
    propios.mkdir()
    Image.new("RGBA", (512, 512), (0, 56, 184, 255)).save(propios / "firefox.png")
    aj = iconos_gen.Ajustes(objetivo="#0038B8", intensidad=1.0, emblema=str(_emblema(tmp_path)))
    destino = tmp_path / "Ultron-x"
    res = iconos_gen.generar("x", aj, destino, base=tema_base, dir_personalizados=propios)
    assert res["generado"]
    # SVG: el naranja pasa a azul y el blanco no cambia
    svg = (destino / "scalable" / "mimetypes" / "text-x-generic.svg").read_text(encoding="utf-8")
    assert "#e95420" not in svg and "#ffffff" in svg
    # carpeta: azul y con emblema blanco en la esquina
    carpeta = Image.open(destino / "48x48" / "places" / "folder.png").convert("RGB")
    r, g, b = carpeta.getpixel((5, 5))
    assert b > r and b > g
    assert carpeta.getpixel((46, 46)) == (255, 255, 255)
    # icono propio en su tamaño
    assert Image.open(destino / "48x48" / "apps" / "firefox.png").size == (48, 48)
    indice = (destino / "index.theme").read_text(encoding="utf-8")
    assert "Name=Ultron-x" in indice and "Inherits=Yaru,Adwaita,hicolor" in indice
    # caché: segunda vez no regenera
    assert iconos_gen.generar("x", aj, destino, base=tema_base,
                              dir_personalizados=propios)["generado"] is False


def test_iconos_monocromo_y_opacidad(tmp_path, tema_base):
    aj = iconos_gen.Ajustes(monocromo=True, opacidad=0.5, objetivo="#E8E8E8")
    destino = tmp_path / "Ultron-f"
    iconos_gen.generar("f", aj, destino, base=tema_base)
    r, g, b, a = Image.open(destino / "48x48" / "apps" / "firefox.png").getpixel((3, 3))
    assert abs(r - g) < 25 and abs(g - b) < 25
    assert a == 128


def test_capa_iconos(ejg, tmp_home, tema_base):
    aplicado = _ciclo(type("CapaIconosPrueba", (), {})
                      if False else _capa_iconos_con_base(tema_base), ejg, "netanyahu")
    assert aplicado[("org.gnome.desktop.interface", "icon-theme")] == "'Ultron-netanyahu'"


def _capa_iconos_con_base(base: Path):
    from ultron.capas.iconos import CapaIconos

    class _Capa(CapaIconos):
        def aplicar(self, cfg):
            super().aplicar({**cfg, "base": str(base)})

    _Capa.nombre = "iconos"
    return _Capa


# --- cursor ---------------------------------------------------------------------------------


def test_xcursor_recolorea():
    pix = bytes([32, 84, 233, 255]) * (4 * 4)  # BGRA naranja
    datos = xcursor.crear([(4, 1, 1, pix)])
    aj = iconos_gen.Ajustes(objetivo="#0038B8", intensidad=1.0, umbral=0.0)
    nuevo = xcursor.recolorear(datos, lambda im: iconos_gen.recolorear_imagen(im, aj, aj.objetivo))
    assert len(nuevo) == len(datos) and nuevo[:4] == b"Xcur"
    b, g, r, a = nuevo[-4:]
    assert b > r and a == 255


def test_generar_cursor(tmp_path):
    base = tmp_path / "Base"
    (base / "cursors").mkdir(parents=True)
    pix = bytes([32, 84, 233, 255]) * 16
    (base / "cursors" / "left_ptr").write_bytes(xcursor.crear([(4, 0, 0, pix)]))
    destino = tmp_path / "Ultron-cursor"
    n = cursor.generar_cursor(base, destino, iconos_gen.Ajustes(objetivo="#00F0FF", umbral=0))
    assert n == 1 and (destino / "cursors" / "left_ptr").exists()
    assert "Inherits=Base" in (destino / "index.theme").read_text(encoding="utf-8")


def test_capa_cursor(ejg):
    aplicado = _ciclo(cursor.CapaCursor, ejg, "presentacion")
    assert aplicado[("org.gnome.desktop.interface", "cursor-size")] == "48"


# --- extensiones ---------------------------------------------------------------------------------


def test_extensiones_no_instaladas_se_saltan(ejg):
    ejg.respuestas[("gnome-extensions", "info")] = __import__(
        "ultron.nucleo.ejecutor", fromlist=["Resultado"]).Resultado(2, "", "no existe")
    capa = extensiones.CapaExtensiones(ejg, _ctx("gaming"))
    previo = capa.capturar({"activar": ["burn-my-windows@schneegans.github.com"]})
    capa.aplicar({"activar": ["burn-my-windows@schneegans.github.com"]})
    assert not ejg.comandos("gnome-extensions enable")
    capa.restaurar(previo)


def test_extensiones_ajustes_dconf(ejg):
    cfg = {"activar": ["x@y"], "ajustes": {"/org/gnome/shell/extensions/x/sigma": "30"}}
    ejg.dconf["/org/gnome/shell/extensions/x/sigma"] = "10"
    capa = extensiones.CapaExtensiones(ejg, _ctx("gaming"))
    previo = capa.capturar(cfg)
    capa.aplicar(cfg)
    assert ejg.dconf["/org/gnome/shell/extensions/x/sigma"] == "30"
    assert ejg.comandos("gnome-extensions enable x@y")
    capa.restaurar(previo)
    assert ejg.dconf["/org/gnome/shell/extensions/x/sigma"] == "10"


# --- sonido / música ------------------------------------------------------------------------------


def test_sonido(ejg, tmp_home):
    aplicado = _ciclo(sonido.CapaSonido, ejg, "gaming")
    assert aplicado[("org.gnome.desktop.sound", "theme-name")] == "'Ultron-gaming'"
    assert not (tmp_home / ".local" / "share" / "sounds" / "Ultron-gaming").exists()


def test_musica_silenciar_persiste_y_se_borra_al_entrar(tmp_home):
    m = registro.obtener("netanyahu")
    mp3 = m.dir_usuario() / "tema" / "musica.mp3"
    mp3.parent.mkdir(parents=True)
    mp3.write_bytes(b"ID3")
    ej = EjecutorFalso(respuestas={("mpv",): "4242"})
    capa = sonido.CapaMusica(ej, _ctx("netanyahu"))
    capa.aplicar(m.capas["musica"])
    assert ej.comandos("mpv") and "--loop-file=inf" in ej.comandos("mpv")[0]
    assert estado.obtener("musica_pid") == 4242
    assert panel.leer()["musica_sonando"] is True
    sonido.silenciar(ej)
    assert estado.obtener("musica_silenciada") is True
    assert panel.leer()["musica_sonando"] is False
    assert panel.leer()["musica_silenciada"] is True
    capa.aplicar(m.capas["musica"])  # volver a entrar
    assert estado.obtener("musica_silenciada") is False
    capa.restaurar({})
    assert estado.obtener("musica_pid") is None


def test_musica_sin_archivo_no_falla(tmp_home):
    ej = EjecutorFalso()
    sonido.CapaMusica(ej, _ctx("netanyahu")).aplicar({"archivo": "tema/no-existe.mp3"})
    assert not ej.comandos("mpv")


def test_netanyahu_trae_su_musica():
    assert (registro.obtener("netanyahu").dir / "tema" / "musica.mp3").is_file()


# --- sistema / hosts ---------------------------------------------------------------------------------


def test_hosts_idempotente_y_reversible(tmp_path):
    original = "127.0.0.1 localhost\n"
    texto = hosts.poner(original, ["youtube.com", "https://www.tiktok.com/x"])
    assert hosts.poner(texto, ["youtube.com", "https://www.tiktok.com/x"]) == texto
    assert "0.0.0.0 www.youtube.com" in texto and "0.0.0.0 www.tiktok.com" in texto
    assert hosts.quitar(texto) == original
    ruta = tmp_path / "hosts"
    ruta.write_text(original, encoding="utf-8")
    ej = EjecutorFalso()
    hosts.bloquear(ej, ["x.com"], ruta=ruta)
    hosts.bloquear(ej, ["x.com"], ruta=ruta)
    assert ruta.read_text(encoding="utf-8").count("0.0.0.0 x.com") == 1
    hosts.desbloquear(ej, ruta=ruta)
    assert ruta.read_text(encoding="utf-8") == original


def test_sistema(ejg):
    aplicado = _ciclo(sistema.CapaSistema, ejg, "presentacion")
    assert aplicado[("org.gnome.desktop.notifications", "show-banners")] == "false"
    assert aplicado[("org.gnome.desktop.session", "idle-delay")] == "uint32 0"
    assert aplicado[("org.gnome.desktop.interface", "text-scaling-factor")] == "1.15"


def test_sistema_privacidad(ejg):
    aplicado = _ciclo(sistema.CapaSistema, ejg, "fantasma")
    assert aplicado[("org.gnome.desktop.privacy", "remember-recent-files")] == "false"


def test_widgets(tmp_home):
    ej = EjecutorFalso(respuestas={("conky",): "777"})
    capa = sistema.CapaWidgets(ej, _ctx("gaming"))
    previo = capa.capturar({})
    capa.aplicar({"fuente": "Orbitron"})
    conf, auto = capa._rutas()
    texto = conf.read_text(encoding="utf-8")
    assert "#FF00E6" in texto and "@@" not in texto and "Orbitron" in texto
    assert auto.exists() and estado.obtener("conky_pid") == 777
    capa.restaurar(previo)
    assert not auto.exists()


# --- arranque ---------------------------------------------------------------------------------


def test_arranque_desactivado_por_defecto(ejg):
    ok, motivo = arranque.CapaArranque(ejg, _ctx("netanyahu")).disponible()
    assert not ok and "--arranque" in motivo


def test_arranque_simulado(monkeypatch):
    monkeypatch.setenv("ULTRON_ARRANQUE", "1")
    ej = EjecutorFalso(simular=True)
    capa = arranque.CapaArranque(ej, _ctx("netanyahu"))
    assert capa.disponible()[0]
    capa.aplicar({})
    texto = " | ".join(ej.comandos())
    assert "update-initramfs -u" in texto and "update-grub" in texto and "dconf update" in texto
    assert "update-alternatives --set default.plymouth" in texto


def test_script_plymouth_pide_clave():
    script = arranque.script_plymouth({"fondo": "#000000", "primario": "#ffffff"})
    assert "SetDisplayPasswordFunction" in script and "logo.png" in script


# --- motor completo con todas las capas ------------------------------------------------------------


@pytest.mark.parametrize("id_modo", ["netanyahu", "focus", "gaming", "presentacion", "fantasma"])
def test_simular_todas_las_capas(id_modo):
    ej = EjecutorFalso(simular=True)
    res = motor.entrar(id_modo, ej=ej)
    aplicadas = {r.nombre for r in res if r.estado == "aplicada"}
    assert {"shell", "escritorio"} <= aplicadas or id_modo == "presentacion"
    assert len(ej.historial) > 5


def test_entrar_y_salir_deja_gsettings_igual(tmp_home, monkeypatch):
    ej = EjecutorFalso(gsettings=dict(GS), respuestas={("mpv",): "1", ("conky",): "2"})
    monkeypatch.setattr(iconos_gen, "base_disponible", lambda bases=None: None)
    antes = dict(ej.gsettings)
    motor.entrar("presentacion", ej=ej)
    assert ej.gsettings != antes
    motor.salir(ej=ej)
    assert ej.gsettings == antes


# --- extensión, carga, comandos ----------------------------------------------------------------


RAIZ = Path(__file__).resolve().parent.parent


def test_metadata_extension():
    meta = json.loads((RAIZ / "extension" / "ultron@ultron" / "metadata.json").read_text("utf-8"))
    assert meta["uuid"] == "ultron@ultron"
    assert {"45", "46", "47", "48"} <= set(meta["shell-version"])


@pytest.mark.skipif(shutil.which("node") is None, reason="sin Node")
def test_extension_js_sintaxis(tmp_path):
    copia = tmp_path / "extension.mjs"
    copia.write_text((RAIZ / "extension" / "ultron@ultron" / "extension.js").read_text("utf-8"),
                     encoding="utf-8")
    r = subprocess.run(["node", "--check", str(copia)], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr


def test_carga_sin_gtk_ejecuta_trabajo(monkeypatch):
    from ultron.ui import carga, tema

    monkeypatch.setenv("ULTRON_SIN_CARGA", "1")
    vistos = []

    def trabajo(progreso):
        progreso("shell", "aplicada")
        vistos.append(1)
        return 42

    assert carga.ejecutar(tema.cargar_tema("gaming"), "GAMING", ["shell"], trabajo) == 42
    assert vistos == [1]


def test_animaciones_carga_dibujan():
    from ultron.ui.carga import dibujar_animacion

    class Cairo:
        def __getattr__(self, _nombre):
            return lambda *a, **k: None

    for m in ("netanyahu", "focus", "gaming", "presentacion", "fantasma", "otro"):
        dibujar_animacion(Cairo(), 800, 600, 1.5, m, {"primario": "#ff00e6", "acento": "#00f0ff"})


def test_comando_importar_musica(tmp_path):
    from ultron.compartidas.musica_tema import comando_importar

    destino = tmp_path / "musica.mp3"
    url = comando_importar("https://youtu.be/x", destino, "0:30", "1:00")
    assert url[0] == "yt-dlp" and "*0:30-1:00" in url and url[-1] == "https://youtu.be/x"
    local = comando_importar("a.wav", destino, None, "2:00")
    assert local[0] == "ffmpeg" and "-to" in local and local[-1] == str(destino)


def test_importar_tema(tmp_path):
    from ultron.compartidas.musica_tema import importar_tema

    origen = tmp_path / "o"
    (origen / "iconos").mkdir(parents=True)
    (origen / "iconos" / "firefox.png").write_bytes(b"x")
    (origen / "fondo.png").write_bytes(b"x")
    (origen / "basura.txt").write_bytes(b"x")
    copiados = importar_tema(origen, tmp_path / "d")
    assert sorted(copiados) == ["fondo.png", "iconos"]


def test_descargar_extension(tmp_path):
    from ultron.compartidas.instalacion import descargar_extension

    def m(req):
        if "extension-info" in str(req.url):
            assert req.url.params["shell_version"] == "46"
            return httpx.Response(200, json={"download_url": "/download/x.zip"})
        return httpx.Response(200, content=b"PK\x03\x04zip")

    zip_ = descargar_extension("x@y", "46", tmp_path, httpx.Client(transport=httpx.MockTransport(m)))
    assert zip_.read_bytes().startswith(b"PK")


def test_plan_dependencias():
    from ultron.nucleo import dependencias

    p = dependencias.plan(["gaming"])
    assert "cava" in p.apt and "mpv" in p.apt
    assert "desktop-cube@schneegans.github.com" in p.extensiones
    assert "Orbitron" in p.fuentes
    assert "nmap" not in p.apt


def test_icono_propio_sustituye_carpetas_y_archivos(tmp_path, tema_base):
    propios = tmp_path / "propios"
    propios.mkdir()
    Image.new("RGBA", (512, 512), (0, 56, 184, 255)).save(propios / "folder.png")
    Image.new("RGBA", (512, 512), (255, 255, 255, 255)).save(propios / "text-x-generic.png")
    destino = tmp_path / "Ultron-y"
    iconos_gen.generar("y", iconos_gen.Ajustes(), destino, base=tema_base,
                       dir_personalizados=propios)
    carpeta = Image.open(destino / "48x48" / "places" / "folder.png").convert("RGB")
    assert carpeta.size == (48, 48) and carpeta.getpixel((24, 24)) == (0, 56, 184)
    assert not (destino / "48x48" / "apps" / "folder.png").exists()
    archivo = destino / "scalable" / "mimetypes" / "text-x-generic.png"
    assert archivo.exists() and not archivo.with_suffix(".svg").exists()
