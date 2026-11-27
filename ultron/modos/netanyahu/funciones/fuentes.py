"""Fuentes OSINT: APIs públicas y herramientas externas que Ultron consulta.

Cada consulta recibe un `httpx.Client` y devuelve un dict; nunca lanza excepciones (si una
fuente cae, devuelve {"aviso": ...} y la operación sigue). Las que necesitan clave la leen de
la configuración (`ultron osint clave <servicio> <clave>`) y, si no está, se saltan.
"""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import subprocess
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any
from urllib.parse import quote, quote_plus, urlparse

import httpx

from ultron.nucleo import config

AGENTE = {"User-Agent": "Ultron-OSINT/1.0 (+https://github.com)"}


@dataclass(frozen=True)
class Fuente:
    nombre: str
    tipo: str  # dominio | ip | url | correo | usuario | imagen
    descripcion: str
    web: str
    clave: str = ""  # servicio en la config si necesita clave


@dataclass(frozen=True)
class Herramienta:
    programa: str
    descripcion: str
    instalar: str


FUENTES: list[Fuente] = [
    Fuente("crt.sh", "dominio", "Subdominios por transparencia de certificados", "https://crt.sh"),
    Fuente("RDAP", "dominio", "Registro del dominio: alta, caducidad, registrador",
           "https://rdap.org"),
    Fuente("DNS", "dominio", "Registros A, AAAA, MX, NS, TXT, CAA y seguridad del correo",
           "dnspython"),
    Fuente("Wayback Machine", "dominio", "Historial de la web desde su primera captura",
           "https://web.archive.org"),
    Fuente("urlscan.io", "dominio", "Escaneos públicos de la web y sus recursos",
           "https://urlscan.io"),
    Fuente("AlienVault OTX", "dominio", "Inteligencia de amenazas (pulsos, malware)",
           "https://otx.alienvault.com"),
    Fuente("HackerTarget", "dominio", "Hosts conocidos del dominio", "https://hackertarget.com"),
    Fuente("Shodan InternetDB", "ip", "Puertos abiertos, servicios y CVE de una IP",
           "https://internetdb.shodan.io"),
    Fuente("ip-api", "ip", "Geolocalización y proveedor", "https://ip-api.com"),
    Fuente("RIPEstat", "ip", "Sistema autónomo, prefijo y contacto de abuso",
           "https://stat.ripe.net"),
    Fuente("GreyNoise", "ip", "¿Escanea Internet? ¿Es ruido o un ataque dirigido?",
           "https://greynoise.io"),
    Fuente("Shodan", "ip", "Banners completos de servicios", "https://shodan.io", "shodan"),
    Fuente("VirusTotal", "url", "Reputación en 70 motores antivirus", "https://virustotal.com",
           "virustotal"),
    Fuente("XposedOrNot", "correo", "Filtraciones en las que aparece un correo",
           "https://xposedornot.com"),
    Fuente("Have I Been Pwned", "correo", "Filtraciones (con clave)", "https://haveibeenpwned.com",
           "hibp"),
    Fuente("Gravatar", "correo", "Perfil público asociado al correo", "https://gravatar.com"),
    Fuente("Perfiles web", "usuario", "Presencia del alias en webs y redes", "sitios.json"),
    Fuente("Búsqueda inversa", "imagen", "Google Lens, Bing, Yandex y TinEye", "navegador"),
    Fuente("EXIF", "imagen", "Cámara, fecha y GPS de una foto", "Pillow / exiftool"),
]

HERRAMIENTAS: list[Herramienta] = [
    Herramienta("subfinder", "Descubrimiento pasivo de subdominios (ProjectDiscovery)",
                "go install github.com/projectdiscovery/subfinder/v2/cmd/subfinder@latest"),
    Herramienta("amass", "Mapa de la superficie de ataque (OWASP)", "sudo snap install amass"),
    Herramienta("theHarvester", "Hosts y subdominios de fuentes públicas",
                "pipx install theHarvester"),
    Herramienta("whatweb", "Tecnologías de una web", "sudo apt install whatweb"),
    Herramienta("nmap", "Puertos y servicios (solo objetivos propios o autorizados)",
                "sudo apt install nmap"),
    Herramienta("maigret", "Alias en más de 3000 webs", "pipx install maigret"),
    Herramienta("sherlock", "Alias en cientos de redes sociales", "pipx install sherlock-project"),
    Herramienta("spiderfoot", "Automatización OSINT con más de 200 módulos",
                "pipx install spiderfoot"),
    Herramienta("exiftool", "Metadatos de cualquier archivo",
                "sudo apt install libimage-exiftool-perl"),
]


# ── utilidades ─────────────────────────────────────────────────────────────────


def seguro(funcion: Callable[..., Any], *args: Any, **kw: Any) -> Any:
    try:
        return funcion(*args, **kw)
    except (httpx.HTTPError, OSError, ValueError, KeyError, TypeError,
            json.JSONDecodeError, subprocess.SubprocessError) as exc:
        return {"aviso": f"fuente no disponible ({type(exc).__name__})"}


def _json(cliente: httpx.Client, url: str, **kw: Any) -> Any:
    r = cliente.get(url, headers={**AGENTE, **kw.pop("headers", {})}, **kw)
    if r.status_code == 404:
        return None
    r.raise_for_status()
    return r.json()


def clave(servicio: str) -> str | None:
    return config.obtener("osint_claves", servicio, None)


def instalada(programa: str) -> bool:
    return shutil.which(programa) is not None


def ejecutar(argv: list[str], timeout: int = 120) -> str:
    r = subprocess.run(argv, capture_output=True, text=True, timeout=timeout, check=False)
    return r.stdout


# ── dominio ────────────────────────────────────────────────────────────────────


def rdap(cliente: httpx.Client, dominio: str) -> dict:
    datos = _json(cliente, f"https://rdap.org/domain/{dominio}", follow_redirects=True) or {}
    eventos = {e.get("eventAction"): e.get("eventDate", "")[:10] for e in datos.get("events", [])}
    registrador = ""
    for ent in datos.get("entities", []):
        if "registrar" in ent.get("roles", []):
            vcard = ent.get("vcardArray", [None, []])[1]
            registrador = next((v[3] for v in vcard if v[0] == "fn"), "")
    return {"alta": eventos.get("registration"), "caduca": eventos.get("expiration"),
            "cambio": eventos.get("last changed"), "registrador": registrador,
            "estado": datos.get("status", [])}


def doh(cliente: httpx.Client, nombre: str, tipo: str) -> list[str]:
    """DNS sobre HTTPS (Cloudflare, y Google de respaldo): funciona igual en cualquier red."""
    for url in ("https://cloudflare-dns.com/dns-query", "https://dns.google/resolve"):
        try:
            d = _json(cliente, url, params={"name": nombre, "type": tipo},
                      headers={"accept": "application/dns-json"})
        except (httpx.HTTPError, ValueError):
            continue
        return [a.get("data", "").strip('"') if tipo != "TXT" else
                a.get("data", "").replace('" "', "").strip('"')
                for a in (d or {}).get("Answer", []) if a.get("type") == TIPOS_DNS[tipo]]
    return []


TIPOS_DNS = {"A": 1, "NS": 2, "CNAME": 5, "SOA": 6, "MX": 15, "TXT": 16, "AAAA": 28, "CAA": 257}


def dns_completo(cliente: httpx.Client, dominio: str) -> dict[str, list[str]]:
    return {t: doh(cliente, dominio, t) for t in ("A", "AAAA", "MX", "NS", "TXT", "CAA")}


def seguridad_correo(dominio: str, cliente: httpx.Client) -> dict:
    def txt(nombre: str) -> list[str]:
        return doh(cliente, nombre, "TXT")

    spf = next((t for t in txt(dominio) if t.lower().startswith("v=spf1")), None)
    dmarc = next((t for t in txt(f"_dmarc.{dominio}") if t.lower().startswith("v=dmarc1")), None)
    politica = re.search(r"p=(\w+)", dmarc or "")
    return {"spf": spf or "NO", "dmarc": dmarc or "NO",
            "suplantable": not spf or not dmarc or (politica and politica.group(1) == "none")}


def wayback(cliente: httpx.Client, dominio: str) -> dict:
    filas = _json(cliente, "https://web.archive.org/cdx/search/cdx",
                  params={"url": dominio, "output": "json", "fl": "timestamp",
                          "collapse": "timestamp:6", "limit": 2000}, timeout=20) or []
    marcas = [f[0] for f in filas[1:]]
    if not marcas:
        return {"capturas": 0}
    fmt = lambda m: f"{m[:4]}-{m[4:6]}"  # noqa: E731
    return {"capturas_mensuales": len(marcas), "primera": fmt(marcas[0]),
            "ultima": fmt(marcas[-1]),
            "enlace": f"https://web.archive.org/web/*/{dominio}"}


def urlscan(cliente: httpx.Client, dominio: str) -> dict:
    datos = _json(cliente, "https://urlscan.io/api/v1/search/",
                  params={"q": f"domain:{dominio}", "size": 10}) or {}
    res = datos.get("results", [])
    return {"escaneos": datos.get("total", len(res)),
            "ultimos": [{"fecha": r.get("task", {}).get("time", "")[:10],
                         "url": r.get("page", {}).get("url"), "ip": r.get("page", {}).get("ip"),
                         "pais": r.get("page", {}).get("country"),
                         "servidor": r.get("page", {}).get("server")} for r in res[:5]]}


def otx(cliente: httpx.Client, tipo: str, valor: str) -> dict:
    seccion = {"dominio": "domain", "ip": "IPv4", "url": "url"}[tipo]
    datos = _json(cliente, f"https://otx.alienvault.com/api/v1/indicators/{seccion}/"
                           f"{quote(valor, safe='')}/general", timeout=15) or {}
    pulsos = datos.get("pulse_info", {})
    return {"pulsos_de_amenaza": pulsos.get("count", 0),
            "campañas": [p.get("name") for p in pulsos.get("pulses", [])[:5]]}


def hackertarget(cliente: httpx.Client, dominio: str) -> list[str]:
    r = cliente.get("https://api.hackertarget.com/hostsearch/", params={"q": dominio},
                    headers=AGENTE)
    r.raise_for_status()
    if "error" in r.text.lower() or "API count" in r.text:
        return []
    return sorted({linea.split(",")[0] for linea in r.text.splitlines() if "," in linea})


def subdominios_externos(dominio: str) -> dict:
    """Subdominios con subfinder o amass si están instalados (modo pasivo)."""
    encontrados: set[str] = set()
    usadas = []
    if instalada("subfinder"):
        encontrados |= set(ejecutar(["subfinder", "-silent", "-d", dominio], 180).split())
        usadas.append("subfinder")
    if instalada("amass"):
        salida = ejecutar(["amass", "enum", "-passive", "-d", dominio], 300)
        encontrados |= {w for w in salida.split() if w.endswith(dominio)}
        usadas.append("amass")
    return {"herramientas": usadas, "subdominios": sorted(encontrados)}


TECNOLOGIAS = {
    "WordPress": ["wp-content", "wp-includes"], "Drupal": ["drupal"], "Joomla": ["joomla"],
    "Shopify": ["cdn.shopify"], "Wix": ["wix.com"], "React": ["react", "__next"],
    "Next.js": ["__next", "_next/static"], "Vue": ["vue", "__nuxt"], "Angular": ["ng-version"],
    "jQuery": ["jquery"], "Bootstrap": ["bootstrap"], "Tailwind": ["tailwind"],
    "Google Analytics": ["googletagmanager", "google-analytics"], "Cloudflare": ["cloudflare"],
    "Hotjar": ["hotjar"], "Stripe": ["js.stripe.com"], "reCAPTCHA": ["recaptcha"],
}


def tecnologias(cliente: httpx.Client, url: str) -> dict:
    r = cliente.get(url, headers=AGENTE, follow_redirects=True)
    texto = r.text[:400000].lower()
    cab = {k.lower(): v for k, v in r.headers.items()}
    tec = sorted(n for n, marcas in TECNOLOGIAS.items() if any(m in texto for m in marcas))
    for cabecera in ("server", "x-powered-by", "via", "x-generator"):
        if cabecera in cab:
            tec.append(f"{cabecera}: {cab[cabecera]}")
    if instalada("whatweb"):
        tec.append("whatweb: " + ejecutar(["whatweb", "--color=never", "-q", url], 60)[:400])
    faltan = [c for c in ("strict-transport-security", "content-security-policy",
                          "x-frame-options", "x-content-type-options", "referrer-policy")
              if c not in cab]
    extra = {}
    for ruta in ("/.well-known/security.txt", "/robots.txt"):
        try:
            rr = cliente.get(url.rstrip("/") + ruta, headers=AGENTE, follow_redirects=True)
            extra[ruta] = rr.text[:600] if rr.status_code == 200 else None
        except httpx.HTTPError:
            extra[ruta] = None
    return {"estado_http": r.status_code, "url_final": str(r.url), "tecnologias": tec,
            "cabeceras_de_seguridad_que_faltan": faltan, **extra}


# ── IP ─────────────────────────────────────────────────────────────────────────


def internetdb(cliente: httpx.Client, ip: str) -> dict:
    datos = _json(cliente, f"https://internetdb.shodan.io/{ip}") or {}
    return {"puertos": datos.get("ports", []), "vulnerabilidades": datos.get("vulns", [])[:20],
            "servicios": datos.get("cpes", [])[:15], "etiquetas": datos.get("tags", []),
            "nombres": datos.get("hostnames", [])[:10]}


def geo(cliente: httpx.Client, ip: str) -> dict:
    return _json(cliente, f"http://ip-api.com/json/{ip}",
                 params={"fields": "status,country,regionName,city,lat,lon,isp,org,as,"
                                   "proxy,hosting,mobile"}) or {}


def ripe(cliente: httpx.Client, ip: str) -> dict:
    base = "https://stat.ripe.net/data"
    red = (_json(cliente, f"{base}/network-info/data.json", params={"resource": ip}) or {})
    red = red.get("data", {})
    abuso = (_json(cliente, f"{base}/abuse-contact-finder/data.json",
                   params={"resource": ip}) or {}).get("data", {})
    return {"asn": red.get("asns", []), "prefijo": red.get("prefix"),
            "contacto_abuso": abuso.get("abuse_contacts", [])}


def greynoise(cliente: httpx.Client, ip: str) -> dict:
    r = cliente.get(f"https://api.greynoise.io/v3/community/{ip}", headers=AGENTE)
    if r.status_code == 404:
        return {"ruido": False, "mensaje": "No se la ha visto escaneando Internet"}
    r.raise_for_status()
    d = r.json()
    return {"ruido": d.get("noise"), "benigna": d.get("riot"),
            "clasificacion": d.get("classification"), "nombre": d.get("name")}


def shodan_completo(cliente: httpx.Client, ip: str) -> dict:
    k = clave("shodan")
    if not k:
        return {"aviso": "sin clave (ultron osint clave shodan <clave>)"}
    d = _json(cliente, f"https://api.shodan.io/shodan/host/{ip}", params={"key": k}) or {}
    return {"sistema": d.get("os"), "organizacion": d.get("org"),
            "servicios": [{"puerto": s.get("port"), "producto": s.get("product"),
                           "version": s.get("version")} for s in d.get("data", [])[:15]]}


# ── URL ────────────────────────────────────────────────────────────────────────

MARCAS = ["google", "paypal", "apple", "microsoft", "amazon", "netflix", "facebook",
          "instagram", "whatsapp", "santander", "bbva", "caixabank", "correos", "dhl",
          "agenciatributaria", "steam", "binance", "coinbase", "outlook", "office365"]


def redirecciones(cliente: httpx.Client, url: str) -> dict:
    r = cliente.get(url, headers=AGENTE, follow_redirects=True)
    cadena = [str(h.url) for h in r.history] + [str(r.url)]
    return {"saltos": cadena, "destino": str(r.url), "estado": r.status_code}


def _distancia(a: str, b: str) -> int:
    previa = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        fila = [i]
        for j, cb in enumerate(b, 1):
            fila.append(min(previa[j] + 1, fila[j - 1] + 1, previa[j - 1] + (ca != cb)))
        previa = fila
    return previa[-1]


def senales_url(url: str) -> list[str]:
    """Pistas de phishing en la propia dirección."""
    p = urlparse(url)
    host = (p.hostname or "").lower()
    senales = []
    if re.fullmatch(r"[\d.]+", host):
        senales.append("usa una IP en vez de un dominio")
    if host.count(".") >= 4:
        senales.append("demasiados subdominios")
    if "xn--" in host:
        senales.append("dominio con caracteres internacionales (posible homógrafo)")
    if "@" in url:
        senales.append("contiene @ (oculta el destino real)")
    if p.scheme != "https":
        senales.append("no usa HTTPS")
    base = host.split(".")[-2] if host.count(".") >= 1 else host
    normal = host.translate(str.maketrans("01345@", "oleasa"))
    trozos = re.split(r"[.\-_]", normal)
    for marca in MARCAS:
        if base == marca:
            continue
        if marca in host:
            senales.append(f"menciona «{marca}» pero el dominio es otro")
        elif marca in normal:
            senales.append(f"imita «{marca}» cambiando letras por números")
        elif any(len(t) > 4 and 0 < _distancia(t, marca) <= 2 for t in trozos):
            senales.append(f"se parece a «{marca}» (typosquatting)")
    if any(t in host for t in (".zip", ".mov", ".top", ".xyz", ".click", ".icu")):
        senales.append("extensión de dominio muy usada en estafas")
    return senales


def virustotal(cliente: httpx.Client, url: str) -> dict:
    k = clave("virustotal")
    if not k:
        return {"aviso": "sin clave (ultron osint clave virustotal <clave>)"}
    import base64

    ident = base64.urlsafe_b64encode(url.encode()).decode().strip("=")
    d = _json(cliente, f"https://www.virustotal.com/api/v3/urls/{ident}",
              headers={"x-apikey": k}) or {}
    return d.get("data", {}).get("attributes", {}).get("last_analysis_stats", {})


# ── correo y alias (solo para informes de huella con consentimiento) ───────────


def xposedornot(cliente: httpx.Client, correo: str) -> dict:
    d = _json(cliente, "https://api.xposedornot.com/v1/breach-analytics",
              params={"email": correo}, timeout=20)
    if not d or not d.get("ExposedBreaches"):
        return {"filtraciones": [], "total": 0}
    detalles = d["ExposedBreaches"].get("breaches_details", [])
    return {"total": len(detalles),
            "filtraciones": [{"nombre": b.get("breach"), "fecha": b.get("xposed_date"),
                              "datos": b.get("xposed_data"), "web": b.get("domain")}
                             for b in detalles],
            "riesgo": (d.get("BreachMetrics", {}).get("risk") or [{}])[0].get("risk_label")}


def hibp(cliente: httpx.Client, correo: str) -> dict:
    k = clave("hibp")
    if not k:
        return {"aviso": "sin clave (ultron osint clave hibp <clave>)"}
    d = _json(cliente, f"https://haveibeenpwned.com/api/v3/breachedaccount/{quote(correo)}",
              params={"truncateResponse": "false"}, headers={"hibp-api-key": k}) or []
    return {"total": len(d), "filtraciones": [{"nombre": b.get("Name"),
                                               "fecha": b.get("BreachDate"),
                                               "datos": ", ".join(b.get("DataClasses", []))}
                                              for b in d]}


def gravatar(cliente: httpx.Client, correo: str) -> dict:
    h = hashlib.sha256(correo.strip().lower().encode()).hexdigest()
    d = _json(cliente, f"https://api.gravatar.com/v3/profiles/{h}")
    if not d:
        return {"perfil_publico": False}
    return {"perfil_publico": True, "nombre": d.get("display_name"),
            "enlaces": [c.get("url") for c in d.get("verified_accounts", [])][:10],
            "foto": d.get("avatar_url")}


def busquedas(nombre: str = "", alias: str = "", correo: str = "") -> dict[str, str]:
    """Búsquedas avanzadas para que la propia persona vea qué sale de ella (no se consultan)."""
    g = "https://www.google.com/search?q="
    salida = {}
    if nombre:
        salida["Nombre exacto"] = g + quote_plus(f'"{nombre}"')
        salida["Documentos con tu nombre"] = g + quote_plus(f'"{nombre}" filetype:pdf')
        salida["Tu nombre en redes"] = g + quote_plus(
            f'"{nombre}" site:linkedin.com OR site:instagram.com OR site:x.com')
    if alias:
        salida["Tu alias"] = g + quote_plus(f'"{alias}"')
    if correo:
        salida["Tu correo publicado"] = g + quote_plus(f'"{correo}"')
        salida["Tu correo en pastes"] = g + quote_plus(f'"{correo}" site:pastebin.com')
    return salida


def alias_externo(alias: str) -> dict:
    """Maigret o Sherlock si están instalados (miles de webs)."""
    if instalada("maigret"):
        salida = ejecutar(["maigret", alias, "--no-color", "--no-progressbar", "-a",
                           "--timeout", "10"], 600)
        enlaces = re.findall(r"\[\+\]\s*([^:]+):\s*(https?://\S+)", salida)
        return {"herramienta": "maigret", "perfiles": [{"sitio": s.strip(), "enlace": u}
                                                       for s, u in enlaces]}
    if instalada("sherlock"):
        salida = ejecutar(["sherlock", alias, "--print-found", "--no-color"], 600)
        enlaces = re.findall(r"\[\+\]\s*([^:]+):\s*(https?://\S+)", salida)
        return {"herramienta": "sherlock", "perfiles": [{"sitio": s.strip(), "enlace": u}
                                                        for s, u in enlaces]}
    return {"herramienta": None}


# ── imagen ─────────────────────────────────────────────────────────────────────


def busqueda_inversa(url_imagen: str) -> dict[str, str]:
    u = quote(url_imagen, safe="")
    return {"Google Lens": f"https://lens.google.com/uploadbyurl?url={u}",
            "Bing Visual": f"https://www.bing.com/images/search?view=detailv2&iss=sbi&q=imgurl:{u}",
            "Yandex": f"https://yandex.com/images/search?rpt=imageview&url={u}",
            "TinEye": f"https://tineye.com/search?url={u}"}
