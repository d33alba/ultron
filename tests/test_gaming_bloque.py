"""Pruebas de aceptación de Gaming sin ejecutar herramientas del sistema."""

from datetime import datetime
from time import perf_counter

import pytest
from falsos import EjecutorFalso
from typer.testing import CliRunner

from ultron.capas.base import Contexto
from ultron.capas.extensiones import HANABI, CapaExtensiones
from ultron.capas.sistema import NOTIF
from ultron.cli import app
from ultron.modos.gaming import generar_recursos
from ultron.modos.gaming.funciones import ajustes, biblioteca, clips
from ultron.nucleo import registro, xp


def test_vdf_acf_y_bibliotecas(tmp_path):
    base = tmp_path / "steamapps"
    base.mkdir()
    secundaria = tmp_path / "otra" / "steamapps"
    secundaria.mkdir(parents=True)
    (base / "libraryfolders.vdf").write_text(
        f'"libraryfolders" {{ // comentario\n "1" {{ "path" "{secundaria.parent.as_posix()}" }} }}',
        encoding="utf-8")
    (secundaria / "appmanifest_42.acf").write_text(
        r'"AppState" { "appid" "42" "name" "Juego \"Neón\"" }', encoding="utf-8")
    juego, = biblioteca.steam(base)
    assert juego.nombre == 'Juego "Neón"'
    assert juego.comando == ("steam", "steam://rungameid/42")
    with pytest.raises(ValueError, match="cerrar"):
        biblioteca.vdf('"raíz" { "clave" "dato"')


def test_desktop_y_busqueda_difusa(tmp_path):
    archivo = tmp_path / "juego.desktop"
    archivo.write_text(
        '[Desktop Entry]\nType=Application\nName=SuperTuxKart\nExec=juego %U\nCategories=Game;\n',
        encoding="utf-8")
    juego = biblioteca.desktop(archivo)
    assert juego.comando == ("gio", "launch", str(archivo))
    assert biblioteca.buscar([juego], "supertuxkrt") == juego
    assert biblioteca.buscar([juego], "1") == juego
    assert biblioteca.buscar([juego], "2") is None
    archivo.write_text(archivo.read_text(encoding="utf-8").replace("Game;", "GameTools;"),
                       encoding="utf-8")
    assert biblioteca.desktop(archivo) is None
    archivo.write_text(
        "[Desktop Entry]\nName=Mi juego\nCategories=Game;\n"
        "Exec=/usr/bin/flatpak run --branch=stable org.ejemplo.Juego\n",
        encoding="utf-8")
    assert biblioteca.desktop(archivo).comando == ("flatpak", "run", archivo.stem)


def test_fondo_determinista_y_medidas():
    inicio = perf_counter()
    a = generar_recursos.fondo(25, 640, 360)
    assert a.size == (640, 360)
    assert a.tobytes() == generar_recursos.fondo(25, 640, 360).tobytes()
    assert a.tobytes() != generar_recursos.fondo(26, 640, 360).tobytes()
    assert generar_recursos.fondo().size == (3840, 2160)
    assert perf_counter() - inicio < 10


def test_xp_niveles_y_logros():
    datos = xp.leer()
    ahora = datetime(2026, 1, 1, 3)
    for modo in ("gaming", "focus", "netanyahu", "fantasma", "presentacion"):
        xp.sumar(datos, "entrar", modo, ahora, 0)
    xp.sumar(datos, "salir", None, ahora, 29)
    for _ in range(10):
        xp.sumar(datos, "osint", None, ahora, 30)
        xp.sumar(datos, "pomodoro_completado", None, ahora, 31)
    assert len(xp.LOGROS) == 15
    assert {"noctambulo", "poliglota", "analista", "empollon", "speedrun"} <= set(datos["logros"])
    assert datos["xp"] == 5 * xp.PUNTOS["entrar"] + xp.PUNTOS["salir"] + 250 + 50
    assert [xp.nivel(v) for v in (0, 49, 50, 199, 200, 450)] == [0, 0, 1, 1, 2, 3]


@pytest.mark.parametrize("simular", [False, True])
def test_turbo_hace_y_deshace(simular):
    ej = EjecutorFalso(
        simular=simular,
        programas={"powerprofilesctl", "systemctl", "gsettings"},
        respuestas={"powerprofilesctl get": "balanced", "systemctl --user is-active": "active"},
        gsettings={(NOTIF, "show-banners"): "true"},
    )
    previo = ajustes.activar(ej)
    assert ajustes.archivo_turbo().is_file() != simular
    ajustes.desactivar(ej, previo)
    assert not ajustes.archivo_turbo().exists()
    assert ["powerprofilesctl", "set", "performance"] in ej.historial
    assert ["powerprofilesctl", "set", "balanced"] in ej.historial
    assert ["systemctl", "--user", "stop", ajustes.MINERO] in ej.historial
    assert ["systemctl", "--user", "start", ajustes.MINERO] in ej.historial
    assert ["gsettings", "set", NOTIF, "show-banners", "false"] in ej.historial
    assert ej.gsettings_get(NOTIF, "show-banners") == "true"


def test_extensiones_gaming_y_restauracion():
    modo = registro.obtener("gaming")
    ej = EjecutorFalso()
    capa = CapaExtensiones(ej, Contexto(modo, modo.dir))
    cfg = modo.capas["extensiones"]
    previo = capa.capturar(cfg)
    capa.aplicar(cfg)
    assert ["gnome-extensions", "disable", HANABI] in ej.historial
    clave = "/org/gnome/shell/extensions/openbar/neon"
    assert ej.dconf[clave] == "true"
    capa.restaurar(previo)
    assert clave not in ej.dconf


def test_turbo_pausa_tracker_simulado():
    ej = EjecutorFalso(simular=True, programas={"tracker3"})
    ajustes.activar(ej)
    assert ["tracker3", "daemon", "--miner", "Files", "--pause-for-process",
            "Ultron Gaming"] in ej.historial
    assert not ajustes.archivo_turbo().exists()


def test_config_y_cli(monkeypatch):
    import ultron.modos.gaming.funciones as comandos

    ej = EjecutorFalso()
    monkeypatch.setattr(comandos, "_ej", lambda: ej)
    cli = CliRunner()
    assert cli.invoke(app, ["fps", "on"]).exit_code == 0
    assert cli.invoke(app, ["visualizador"]).exit_code == 0
    assert ej.historial[-1][:2] == ["cava", "-p"]
    assert "position=top-left" in ajustes.MANGOHUD
    for color in ("FF00E6", "8A2BE2", "00F0FF"):
        assert color in ajustes.CAVA
    resultado = cli.invoke(app, ["hud", "--demo", "--una-vez"])
    assert resultado.exit_code == 0 and "HUD DEL SISTEMA" in resultado.stdout
    assert xp.leer()["usos"]["hud"] == 1
    assert cli.invoke(app, ["--simular", "juegos", "--demo"]).exit_code == 0
    assert "juegos" not in xp.leer()["usos"]
    assert cli.invoke(app, ["juegos", "--demo", "999"]).exit_code == 1


def test_segmentos_y_concatenacion(tmp_path):
    for numero in range(10):
        (tmp_path / f"tramo-{numero:02}.mkv").touch()
    (tmp_path / "captura.mkv").touch()
    ultim = clips.segmentos(tmp_path, 12)
    assert [p.stem for p in ultim] == ["tramo-07", "tramo-08", "tramo-09"]
    comando = clips.concatenacion(ultim, tmp_path / "salida.mkv", 12)
    assert comando[comando.index("-ss") + 1] == "3"
    assert comando[comando.index("-t") + 1] == "12"
    lista = clips.lista_concat(ultim)
    assert lista.index("tramo-07") < lista.index("tramo-08") < lista.index("tramo-09")
    assert "captura" not in lista


def test_grabador_simulado(monkeypatch):
    monkeypatch.setenv("XDG_SESSION_TYPE", "wayland")
    ej = EjecutorFalso(simular=True, programas={"gpu-screen-recorder"})
    assert "25 s" in clips.iniciar(ej, 25)
    assert ej.historial[0][:7] == ["gpu-screen-recorder", "-w", "portal", "-f", "60", "-r", "25"]
    assert not clips.carpeta().exists()

