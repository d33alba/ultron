from __future__ import annotations

import pytest

from ultron.capas.base import REGISTRO_CAPAS, Capa, cargar_capas
from ultron.nucleo import estado, motor

SISTEMA: dict[str, int] = {}
EVENTOS: list[str] = []


class _CapaFalsa(Capa):
    def capturar(self, cfg):
        EVENTOS.append(f"capturar:{self.nombre}")
        # la instantánea ya debe estar en disco con esta capa antes de aplicar
        return {"valor": SISTEMA.get(self.nombre, 0)}

    def aplicar(self, cfg):
        if not self.ej.simular:
            inst = motor.leer_instantanea()
            assert inst and inst["capas"][-1]["nombre"] == self.nombre
        EVENTOS.append(f"aplicar:{self.nombre}")
        SISTEMA[self.nombre] = cfg.get("valor", 99)
        if cfg.get("fallar"):
            raise RuntimeError("boom")

    def restaurar(self, previo):
        EVENTOS.append(f"restaurar:{self.nombre}")
        SISTEMA[self.nombre] = previo["valor"]


class CapaA(_CapaFalsa):
    nombre = "falsa_a"
    orden = 10


class CapaB(_CapaFalsa):
    nombre = "falsa_b"
    orden = 20


class CapaSudo(_CapaFalsa):
    nombre = "falsa_sudo"
    orden = 30
    requiere_sudo = True


class CapaNoDisponible(_CapaFalsa):
    nombre = "falsa_nd"
    orden = 5

    def disponible(self):
        return False, "no hay GNOME"


@pytest.fixture(autouse=True)
def capas_falsas():
    cargar_capas()
    SISTEMA.clear()
    EVENTOS.clear()
    for cls in (CapaA, CapaB, CapaSudo, CapaNoDisponible):
        REGISTRO_CAPAS[cls.nombre] = cls
    yield
    for cls in (CapaA, CapaB, CapaSudo, CapaNoDisponible):
        REGISTRO_CAPAS.pop(cls.nombre, None)


def test_orden_y_estado(modo_prueba, ej):
    # en el YAML b va antes que a, pero el orden de la capa manda
    modo = modo_prueba("  falsa_b: {valor: 2}\n  falsa_a: {valor: 1}\n")
    res = motor.entrar(modo, ej=ej)
    assert [r.nombre for r in res] == ["falsa_a", "falsa_b"]
    assert EVENTOS == ["capturar:falsa_a", "aplicar:falsa_a", "capturar:falsa_b", "aplicar:falsa_b"]
    assert estado.modo_activo() == "prueba"
    assert SISTEMA == {"falsa_a": 1, "falsa_b": 2}


def test_salir_restaura_en_orden_inverso(modo_prueba, ej):
    motor.entrar(modo_prueba(), ej=ej)
    EVENTOS.clear()
    motor.salir(ej=ej)
    assert EVENTOS == ["restaurar:falsa_b", "restaurar:falsa_a"]
    assert SISTEMA == {"falsa_a": 0, "falsa_b": 0}
    assert estado.modo_activo() is None
    assert motor.leer_instantanea() is None


def test_rollback_si_falla(modo_prueba, ej):
    modo = modo_prueba("  falsa_a: {valor: 1}\n  falsa_b: {valor: 2, fallar: true}\n")
    with pytest.raises(motor.ErrorMotor, match="falsa_b"):
        motor.entrar(modo, ej=ej)
    assert SISTEMA == {"falsa_a": 0, "falsa_b": 0}
    assert EVENTOS[-2:] == ["restaurar:falsa_b", "restaurar:falsa_a"]
    assert estado.modo_activo() is None
    assert motor.leer_instantanea() is None


def test_recuperacion_tras_corte(modo_prueba, ej):
    """Si el proceso muere a medias, salir() restaura con la instantánea del disco."""
    modo = modo_prueba()

    class Corte(Exception):
        pass

    original = CapaB.aplicar

    def cortar(self, cfg):
        raise Corte()

    CapaB.aplicar = cortar
    try:
        # simulamos que el proceso muere: la excepción no es capturada por el rollback
        # porque saltamos el motor y escribimos la instantánea como lo haría un corte
        motor._guardar_instantanea(
            {"modo": modo, "capas": [{"nombre": "falsa_a", "previo": {"valor": 0}}]}
        )
        SISTEMA["falsa_a"] = 1
    finally:
        CapaB.aplicar = original
    motor.salir(ej=ej)
    assert SISTEMA["falsa_a"] == 0
    assert motor.leer_instantanea() is None


def test_entrar_en_otro_modo_sale_primero(modo_prueba, ej, tmp_home):
    motor.entrar(modo_prueba(), ej=ej)
    d = tmp_home / ".local" / "share" / "ultron" / "modos" / "otro"
    d.mkdir(parents=True)
    (d / "modo.yaml").write_text("id: otro\nnombre: OTRO\ncapas:\n  falsa_a: {valor: 7}\n",
                                 encoding="utf-8")
    from ultron.nucleo import registro

    registro.invalidar()
    EVENTOS.clear()
    motor.entrar("otro", ej=ej)
    assert EVENTOS[:2] == ["restaurar:falsa_b", "restaurar:falsa_a"]
    assert SISTEMA["falsa_a"] == 7
    assert SISTEMA["falsa_b"] == 0
    assert estado.modo_activo() == "otro"


def test_simular_no_toca_nada(modo_prueba):
    from falsos import EjecutorFalso

    ej = EjecutorFalso(simular=True)
    motor.entrar(modo_prueba(), ej=ej)
    assert motor.leer_instantanea() is None
    assert estado.modo_activo() is None


def test_capas_no_disponibles_y_desconocidas(modo_prueba, ej):
    modo = modo_prueba("  falsa_nd: {}\n  inventada: {}\n  falsa_a: {valor: 1}\n")
    res = {r.nombre: r for r in motor.entrar(modo, ej=ej)}
    assert res["falsa_nd"].estado == "saltada"
    assert "GNOME" in res["falsa_nd"].motivo
    assert res["inventada"].estado == "saltada"
    assert res["falsa_a"].estado == "aplicada"


def test_sudo_rechazado_se_salta(modo_prueba, ej):
    modo = modo_prueba("  falsa_a: {valor: 1}\n  falsa_sudo: {valor: 3}\n")
    pedidas = []
    res = {r.nombre: r for r in motor.entrar(
        modo, ej=ej, confirmar_sudo=lambda capas: pedidas.append(capas) or False)}
    assert pedidas == [["falsa_sudo"]]
    assert res["falsa_sudo"].estado == "saltada"
    assert "falsa_sudo" not in SISTEMA


def test_solo_y_excepto(modo_prueba, ej):
    modo = modo_prueba()
    res = motor.entrar(modo, ej=ej, solo=["falsa_b"])
    assert [r.nombre for r in res] == ["falsa_b"]
    motor.salir(ej=ej)
    res = motor.entrar(modo, ej=ej, excepto=["falsa_b"])
    assert [r.nombre for r in res] == ["falsa_a"]
