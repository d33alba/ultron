"""Herramientas del sistema sin sudo: .deb del USB desempaquetados en el usuario."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from tests.falsos import EjecutorFalso
from ultron.nucleo import herramientas as H

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import preparar_herramientas as P  # noqa: E402


def _paq(nombre, deps="", provides="", version="1.0"):
    return {"Package": nombre, "Version": version, "Depends": deps, "Provides": provides,
            "Filename": f"pool/{nombre}_{version}_amd64.deb", "SHA256": "x", "Size": "10"}


def test_resolver_salta_lo_instalado_y_las_alternativas():
    paquetes = {n["Package"]: n for n in [
        _paq("nmap", "libc6, nmap-common (= 1.0), liblua5.3-0 | liblua-dummy"),
        _paq("nmap-common"), _paq("libc6"), _paq("liblua5.3-0", "libc6"),
        _paq("exif", "perl-api | perlapi-5.34"), _paq("perl-base", provides="perlapi-5.34"),
    ]}
    cierre = P.resolver(["nmap", "exif"], paquetes, P.proveedores(paquetes),
                        base={"libc6", "perl-base"})
    assert sorted(cierre["nmap"]) == ["liblua5.3-0", "nmap", "nmap-common"]
    assert cierre["exif"] == ["exif"]  # perlapi lo provee perl-base, ya instalado


def test_version_mas_nueva_gana():
    assert P._clave_version("1.2.10") > P._clave_version("1.2.9")
    assert P._clave_version("1.0~rc1") < P._clave_version("1.0")


def test_no_se_empaqueta_lo_de_gnome_ni_node():
    lista = H.empaquetables()
    assert "nmap" in lista and "tesseract-ocr" in lista
    assert not {"gnome-tweaks", "nodejs", "npm", "plymouth-themes"} & set(lista)


def test_presente_por_apt_por_usb_o_por_programa(monkeypatch, tmp_path):
    monkeypatch.setattr(H, "prefijo", lambda: tmp_path)
    (tmp_path / "instalados.json").write_text(json.dumps({"whois": ["whois.deb"]}))
    ej = EjecutorFalso(respuestas={"dpkg-query -W -f=${Status} jq": "install ok installed"},
                       programas={"dpkg-query", "node"})
    assert H.presente(ej, "whois")          # desempaquetado del USB
    assert H.presente(ej, "jq")             # instalado con apt
    assert H.presente(ej, "nodejs")         # Node portátil de Ultron
    assert H.faltan(ej, ["whois", "jq", "nmap"]) == ["nmap"]


def test_instalar_desde_usb_desempaqueta_cada_deb_una_vez(monkeypatch, tmp_path):
    monkeypatch.setattr(H, "prefijo", lambda: tmp_path / "sistema")
    offline = tmp_path / "usb"
    (offline / "debs").mkdir(parents=True)
    (offline / "debs" / "lista.json").write_text(json.dumps(
        {"nmap": ["nmap.deb", "liblua.deb"], "lua-tool": ["liblua.deb"]}))
    ej = EjecutorFalso(simular=True)
    hechos, sin = H.instalar_desde_usb(ej, offline, ["nmap", "lua-tool", "raro"])
    assert hechos == ["nmap", "lua-tool"] and sin == ["raro"]
    extraidos = [c[2] for c in ej.historial if c[:2] == ["dpkg-deb", "-x"]]
    assert sorted(Path(x).name for x in extraidos) == ["liblua.deb", "nmap.deb"]


def test_activar_path_pone_los_lanzadores_delante(monkeypatch, tmp_path):
    monkeypatch.setattr(H, "dir_bin", lambda: tmp_path)
    monkeypatch.setenv("PATH", "/usr/bin")
    H.activar_path()
    H.activar_path()
    assert H.os.environ["PATH"].split(H.os.pathsep) == [str(tmp_path), "/usr/bin"]


@pytest.mark.skipif(sys.platform == "win32", reason="lanzadores y enlaces de Linux")
def test_lanzadores_y_recolocar(monkeypatch, tmp_path):
    p = tmp_path / "sistema"
    monkeypatch.setattr(H, "prefijo", lambda: p)
    monkeypatch.setattr(H, "dir_bin", lambda: p / "bin")
    monkeypatch.setenv("HOME", str(tmp_path))
    (p / "usr/bin").mkdir(parents=True)
    (p / "usr/share/raro-ultron").mkdir(parents=True)
    (p / "usr/bin/ruby-ultron-test").write_text("binario")
    script = p / "usr/bin/herramienta"
    script.write_text("#!/usr/bin/ruby-ultron-test -w\nload '/usr/share/raro-ultron/x.rb'\n")
    script.chmod(0o755)
    (p / "usr/bin/ruby-ultron-test").chmod(0o755)
    nombres = H.crear_lanzadores(EjecutorFalso())
    assert "herramienta" in nombres
    lanzador = (p / "bin/herramienta").read_text()
    assert f'"{p}/usr/bin/ruby-ultron-test" -w "{script}"' in lanzador
    assert str(p / "usr/share/raro-ultron/x.rb") in script.read_text()
    assert (tmp_path / ".local/bin/herramienta").is_symlink()
