"""OSINT ampliado: tipos de objetivo, phishing, puntuaciones y dossier (sin red)."""

from __future__ import annotations

import httpx
import pytest

from ultron.modos.netanyahu.funciones import dossier, fuentes, inteligencia


@pytest.mark.parametrize("valor,tipo", [("ubuntu.com", "dominio"), ("8.8.8.8", "ip"),
                                        ("https://a.b/c", "url")])
def test_tipo_objetivo(valor, tipo):
    assert inteligencia.tipo_objetivo(valor) == tipo


def test_tipo_objetivo_invalido():
    with pytest.raises(ValueError):
        inteligencia.tipo_objetivo("no es nada")


def test_senales_phishing():
    assert any("paypal" in s for s in fuentes.senales_url("http://paypa1-login.xyz/"))
    assert any("microsoft" in s for s in fuentes.senales_url("https://micr0soft-help.com"))
    assert fuentes.senales_url("https://www.paypal.com/") == []


def test_evaluar_infra_cuenta_cve_una_vez():
    r = {"Shodan InternetDB · 1": {"vulnerabilidades": ["CVE-1", "CVE-2"], "puertos": [3389]},
         "Shodan InternetDB · 2": {"vulnerabilidades": ["CVE-1"], "puertos": []},
         "Correo (SPF/DMARC)": {"suplantable": True}}
    puntos, hall, recs = inteligencia.evaluar_infra(r)
    assert 0 < puntos <= 100
    assert sum("vulnerabilidades" in t for _n, t in hall) == 1
    assert any("DMARC" in x for x in recs)


def test_evaluar_huella():
    r = {"Filtraciones (XposedOrNot)": {"filtraciones": [{"nombre": "A"}, {"nombre": "B"}]},
         "Perfiles del alias": {"total": 3},
         "Fotos": {"f.jpg": {"GPS": {"lat": 1}}}}
    puntos, hall, recs = inteligencia.evaluar_huella(r)
    assert puntos >= 40 and any("GPS" in t for _n, t in hall)


def test_fuentes_no_lanzan():
    def roto(_c):
        raise httpx.ConnectError("x")

    assert "aviso" in fuentes.seguro(roto, None)


def test_doh_lee_respuestas():
    def manejador(peticion):
        return httpx.Response(200, json={"Answer": [{"type": 1, "data": "1.2.3.4"},
                                                    {"type": 5, "data": "x."}]})

    with httpx.Client(transport=httpx.MockTransport(manejador)) as c:
        assert fuentes.doh(c, "a.com", "A") == ["1.2.3.4"]


def test_dossier(tmp_path):
    ruta = dossier.generar(tmp_path / "d.html", titulo="DOSSIER", objetivo="a.com",
                           tipo="DOMINIO", puntuacion=42, hallazgos=[("alto", "<x>")],
                           recomendaciones=["r"], secciones={"DNS": {"A": ["1.2.3.4"]}})
    texto = ruta.read_text(encoding="utf-8")
    assert "&lt;x&gt;" in texto and "1.2.3.4" in texto and "42" in texto
