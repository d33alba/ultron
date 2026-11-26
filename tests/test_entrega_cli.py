from __future__ import annotations

import re
import shlex
from contextlib import ExitStack
from pathlib import Path
from types import SimpleNamespace

import pytest
from typer.main import get_command
from typer.testing import CliRunner

from ultron import cli
from ultron.compartidas import instalacion
from ultron.nucleo import entrega, motor, registro, rutas
from ultron.nucleo.dependencias import _deps
from ultron.nucleo.doctor import Chequeo, OpcionesDoctor
from ultron.nucleo.ejecutor import Resultado
from ultron.nucleo.esquema import ErrorEsquema

runner = CliRunner()


def test_comandos_documentados_en_readme():
    archivo = Path(__file__).resolve().parents[1] / "README.md"
    comandos = re.findall(
        r"`(ultron(?: [^`\n]+)?)`|^(ultron(?: [^\n]+)?)$",
        archivo.read_text(encoding="utf-8"), re.MULTILINE,
    )
    assert len(comandos) >= 18
    raiz = get_command(cli.app)
    for en_linea, en_bloque in comandos:
        args = shlex.split(en_linea or en_bloque)[1:]
        with ExitStack() as pila:
            comando = raiz
            contexto = pila.enter_context(raiz.make_context("ultron", list(args)))
            while args and getattr(comando, "commands", None) and not args[0].startswith("-"):
                nombre, *args = args
                comando = comando.get_command(contexto, nombre)
                assert comando is not None, en_linea or en_bloque
                contexto = pila.enter_context(
                    comando.make_context(nombre, list(args), parent=contexto)
                )


def test_modo_nuevo_desde_cli(tmp_home):
    destino = rutas.modos_usuario() / "lectura"
    prueba = runner.invoke(cli.app, ["--simular", "modos", "nuevo", "lectura"])
    assert prueba.exit_code == 0, prueba.output
    assert not destino.exists()
    crear = runner.invoke(cli.app, ["modos", "nuevo", "lectura"])
    assert crear.exit_code == 0, crear.output
    assert registro.obtener("lectura").dir == destino
    assert (destino / "tema").is_dir()
    assert 'id = "lectura"' in (destino / "tema.toml").read_text(encoding="utf-8")
    detalle = runner.invoke(cli.app, ["modos", "--detalle", "lectura"])
    assert detalle.exit_code == 0, detalle.output
    duplicado = runner.invoke(cli.app, ["modos", "nuevo", "lectura"])
    assert "Ya existe" in str(duplicado.exception)
    assert (destino / "modo.yaml").is_file()


@pytest.mark.parametrize("invalido", ["../fuga", "a", "FOCUS", "prueba\n"])
def test_rechaza_ids_invalidos(invalido):
    with pytest.raises(ErrorEsquema):
        entrega.crear_modo(invalido)


def test_demo_completa_sin_red_ni_cambios(monkeypatch):
    def prohibido(*args, **kwargs):
        pytest.fail("La demostración sin terminal no debe activar capas ni consultar la IA.")

    monkeypatch.setattr(entrega.motor, "entrar", prohibido)
    monkeypatch.setattr("ultron.ia.cliente.obtener_cliente", prohibido)
    monkeypatch.setattr("httpx.Client", prohibido)
    resultado = runner.invoke(cli.app, ["demo"])
    assert resultado.exit_code == 0, resultado.exception
    for comandos in entrega.DEMOSTRACIONES.values():
        for args in comandos:
            assert args[0] in resultado.output
    rapida = runner.invoke(cli.app, ["demo", "--rapida"])
    assert rapida.exit_code == 0, rapida.exception
    assert "ultron stats --demo" in rapida.output
    assert "ultron repasar --demo" not in rapida.output


def test_demo_restaura_si_falla_un_ejemplo(monkeypatch):
    acciones = []
    tty = SimpleNamespace(isatty=lambda: True)
    monkeypatch.setattr(entrega, "sys", SimpleNamespace(stdin=tty, stdout=tty))
    monkeypatch.setattr(entrega.typer, "confirm", lambda *a, **kw: True)
    monkeypatch.setattr(entrega.motor, "entrar", lambda modo, **kw: acciones.append(modo))
    monkeypatch.setattr(entrega.motor, "salir", lambda: acciones.append("salir") or [])

    def fallo(args):
        raise RuntimeError("Falló el ejemplo")

    with pytest.raises(RuntimeError, match="ejemplo"):
        entrega.recorrer(fallo, rapida=False, simular=False)
    assert acciones == ["netanyahu", "salir"]


def test_doctor_completo_muestra_comandos(monkeypatch):
    monkeypatch.setattr(cli, "ejecutar_doctor", lambda *a: [Chequeo("IA", "ok")])
    completo = runner.invoke(cli.app, ["doctor", "--completo"])
    assert completo.exit_code == 0
    assert "Listo para corregir" in completo.output

    chequeos = [Chequeo("IA", "aviso", "Modelo pendiente", "ultron ia configurar")]
    monkeypatch.setattr(cli, "ejecutar_doctor", lambda *a: chequeos)
    incompleto = runner.invoke(cli.app, ["doctor", "--completo"])
    assert incompleto.exit_code == 2
    assert "ultron ia configurar" in incompleto.output


def test_doctor_por_modo_con_extension_incompatible(ej):
    ej.respuestas = {
        ("dpkg-query",): "install ok installed",
        ("dpkg-query", "-W", "-f=${Status}", "cava"): Resultado(1, "", ""),
        ("gnome-extensions", "list"): "ultron@ultron\nburn-my-windows@schneegans.github.com\n",
        ("env", "LC_ALL=C", "gnome-extensions", "info",
         "burn-my-windows@schneegans.github.com"): "State: OUT OF DATE\n",
        ("env", "LC_ALL=C", "gnome-extensions", "info", "ultron@ultron"): "State: ACTIVE\n",
    }
    resultados = _deps(ej, OpcionesDoctor(completo=True))
    assert any(r.solucion == "sudo apt install cava" for r in resultados)
    assert any(r.detalle == "Versión incompatible" for r in resultados)
    assert any("ultron@ultron" in r.nombre and r.estado == "ok" for r in resultados)
    assert len([r for r in resultados if r.nombre.startswith("Paquetes apt")]) == 5
    assert not ej.historial


def test_instalar_simulado_por_modo(monkeypatch, ej):
    ej.simular = True
    monkeypatch.setattr(instalacion, "Ejecutor", lambda **kwargs: ej)
    resultado = runner.invoke(cli.app, ["instalar", "--modo", "focus", "--simular"])
    assert resultado.exit_code == 0, resultado.exception
    paquetes, = ej.comandos("sudo apt-get install")
    assert "poppler-utils" in paquetes.split()
    assert "mangohud" not in paquetes.split()
    assert ["gnome-extensions", "enable", "ultron@ultron"] in ej.historial
    assert not instalacion.ruta_instaladas().exists()


def test_salida_conserva_la_captura_para_reintentar(modo_prueba, ej, monkeypatch):
    identificador = modo_prueba()
    captura = {"nombre": "falsa_a", "previo": {"valor": 3}}
    motor._guardar_instantanea({"modo": identificador, "capas": [captura]})
    fallida = motor.ResultadoCapa("falsa_a", "fallida")
    monkeypatch.setattr(motor, "_restaurar_lista", lambda *args: [fallida])
    assert motor.salir(ej=ej) == [fallida]
    assert motor.leer_instantanea()["capas"] == [captura]
    with pytest.raises(motor.ErrorMotor, match="Restaura primero"):
        motor.entrar("focus", ej=ej)
    restaurada = motor.ResultadoCapa("falsa_a", "restaurada")
    monkeypatch.setattr(motor, "_restaurar_lista", lambda *args: [restaurada])
    assert motor.salir(ej=ej) == [restaurada]
    assert motor.leer_instantanea() is None
