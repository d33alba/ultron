from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))

from falsos import EjecutorFalso  # noqa: E402

from ultron.nucleo import registro  # noqa: E402
from ultron.ui import tema  # noqa: E402


@pytest.fixture(autouse=True)
def tmp_home(tmp_path, monkeypatch):
    """HOME y XDG_* temporales para que ningún test toque el sistema real."""
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(home / ".config"))
    monkeypatch.setenv("XDG_STATE_HOME", str(home / ".local" / "state"))
    monkeypatch.setenv("XDG_DATA_HOME", str(home / ".local" / "share"))
    monkeypatch.setenv("XDG_CACHE_HOME", str(home / ".cache"))
    monkeypatch.setenv("ULTRON_SIN_ANIMACIONES", "1")
    monkeypatch.setenv("ULTRON_SIN_AUTODETECCION", "1")
    for var in ("ULTRON_PROVEEDOR", "ULTRON_URL_BASE", "ULTRON_MODELO", "ULTRON_API_KEY"):
        monkeypatch.delenv(var, raising=False)
    registro.invalidar()
    tema.invalidar()
    yield home
    registro.invalidar()
    tema.invalidar()


@pytest.fixture
def ej():
    return EjecutorFalso()


@pytest.fixture
def modo_prueba(tmp_home):
    """Crea un modo de usuario «prueba» con capas falsas a y b."""
    def crear(capas: str = "  falsa_a: {valor: 1}\n  falsa_b: {valor: 2}\n") -> str:
        d = tmp_home / ".local" / "share" / "ultron" / "modos" / "prueba"
        d.mkdir(parents=True, exist_ok=True)
        (d / "modo.yaml").write_text(
            "id: prueba\nnombre: PRUEBA\nlema: test\ncapas:\n" + capas, encoding="utf-8"
        )
        registro.invalidar()
        return "prueba"

    return crear
