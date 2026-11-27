"""Operaciones OSINT completas: infraestructura, verificación, huella digital y dossier.

- `osint operacion <dominio|ip|url>`: lanza todas las fuentes a la vez con un panel en
  directo, puntúa la exposición, guarda la operación, genera el dossier y la sitúa en el
  Ojo de Dios.
- `osint url`: ¿es fiable este enlace? (redirecciones, phishing, reputación).
- `osint imagen`: EXIF/GPS y búsqueda inversa en cuatro buscadores.
- `osint huella`: informe de huella digital de una persona **que lo ha pedido o autorizado**
  (o de uno mismo). Sin esa confirmación no se ejecuta.
- `osint fuentes` y `osint clave`: qué fuentes y herramientas hay y claves opcionales.
"""

from __future__ import annotations

import asyncio
import ipaddress
import json
import re
import socket
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path
from typing import Any

import httpx
import typer
from rich.live import Live
from rich.text import Text

from ultron.nucleo import config, rutas

from . import dossier
from . import fuentes as F
from .comun import ejecutor, fallo, guardar, interfaz, mostrar

Consulta = Callable[[httpx.Client], Any]


def tipo_objetivo(objetivo: str) -> str:
    objetivo = objetivo.strip()
    if re.match(r"^https?://", objetivo, re.I):
        return "url"
    try:
        ipaddress.ip_address(objetivo)
        return "ip"
    except ValueError:
        pass
    if re.fullmatch(r"(?=.{1,253}$)([a-z0-9-]{1,63}\.)+[a-z]{2,63}", objetivo.lower()):
        return "dominio"
    raise ValueError("Escribe un dominio (ejemplo.com), una IP pública o una URL (https://…).")


# ── panel en directo ───────────────────────────────────────────────────────────


def _panel(estados: dict[str, str], objetivo: str, t0: float) -> Any:
    t = interfaz()
    tabla = t.tabla("Fuente", "Estado", titulo=f"OPERACIÓN · {objetivo}")
    marcas = {"…": ("⟳ consultando", "aviso"), "ok": ("✔ datos", "ok"),
              "vacío": ("○ sin datos", "apagado"), "error": ("✖ no disponible", "error")}
    for nombre, estado in estados.items():
        texto, estilo = marcas.get(estado, (estado, "texto"))
        tabla.add_row(Text(nombre), Text(texto, style=estilo))
    hechas = sum(e != "…" for e in estados.values())
    pie = f"{hechas}/{len(estados)} fuentes · {time.monotonic() - t0:4.1f} s"
    return t.panel(tabla, titulo=pie)


def ejecutar_fuentes(consultas: dict[str, Consulta], objetivo: str,
                     en_vivo: bool = True) -> dict[str, Any]:
    """Lanza las consultas en paralelo; enseña cómo van llegando los resultados."""
    estados = {n: "…" for n in consultas}
    resultados: dict[str, Any] = {}
    t0 = time.monotonic()
    with httpx.Client(timeout=12, follow_redirects=False) as cliente, \
            ThreadPoolExecutor(max_workers=10) as grupo:
        futuros = {grupo.submit(F.seguro, f, cliente): n for n, f in consultas.items()}
        vivo = Live(_panel(estados, objetivo, t0), console=interfaz().consola,
                    refresh_per_second=8, transient=False) if en_vivo else None
        if vivo:
            vivo.start()
        try:
            for futuro in futuros:
                nombre = futuros[futuro]
                valor = futuro.result()
                resultados[nombre] = valor
                if isinstance(valor, dict) and set(valor) == {"aviso"}:
                    estados[nombre] = "error"
                else:
                    estados[nombre] = "ok" if valor not in (None, [], {}) else "vacío"
                if vivo:
                    vivo.update(_panel(estados, objetivo, t0))
        finally:
            if vivo:
                vivo.stop()
    return resultados


# ── evaluación ─────────────────────────────────────────────────────────────────


def evaluar_infra(r: dict[str, Any]) -> tuple[int, list[tuple[str, str]], list[str]]:
    """Puntuación de exposición 0-100, hallazgos (nivel, texto) y recomendaciones."""
    puntos, hall, recs = 0, [], []
    todas: set[str] = set()
    for nombre, datos in r.items():
        if nombre.startswith("Shodan InternetDB") and isinstance(datos, dict):
            todas |= set(datos.get("vulnerabilidades", []))
    if todas:
        puntos += min(35, 4 * len(todas))
        hall.append(("alto", f"{len(todas)} vulnerabilidades conocidas en sus servidores "
                             f"({', '.join(sorted(todas)[:4])}…)"))
        recs.append("Actualiza los servicios expuestos con CVE conocidos.")
    for nombre, datos in r.items():
        if not isinstance(datos, dict):
            continue
        if nombre.startswith("Shodan InternetDB"):
            puertos = datos.get("puertos", [])
            riesgo = [p for p in puertos if p in (21, 22, 23, 445, 3306, 3389, 5432, 5900,
                                                  6379, 9200, 27017)]
            if riesgo:
                puntos += 6 * len(riesgo)
                hall.append(("medio", f"{nombre}: puertos sensibles abiertos {riesgo}"))
                recs.append("Cierra o filtra con cortafuegos los puertos de administración "
                            "y bases de datos.")
        if nombre == "Correo (SPF/DMARC)" and datos.get("suplantable"):
            puntos += 15
            hall.append(("medio", "El dominio se puede suplantar por correo (SPF/DMARC "
                                  "ausente o en p=none)."))
            recs.append("Publica SPF y DMARC con p=quarantine o p=reject.")
        if nombre == "Tecnologías web":
            faltan = datos.get("cabeceras_de_seguridad_que_faltan", [])
            if len(faltan) >= 3:
                puntos += 10
                hall.append(("bajo", f"Faltan cabeceras de seguridad: {', '.join(faltan)}"))
                recs.append("Añade HSTS, CSP y X-Frame-Options en el servidor web.")
        if nombre.startswith("AlienVault OTX") and datos.get("pulsos_de_amenaza"):
            puntos += 10
            hall.append(("medio", f"Citado en {datos['pulsos_de_amenaza']} informes de "
                                  "amenazas de OTX (revisa si es víctima, origen o mención)."))
        if nombre.startswith("GreyNoise") and datos.get("clasificacion") == "malicious":
            puntos += 25
            hall.append(("alto", "GreyNoise la clasifica como maliciosa."))
    subs = r.get("Subdominios", {})
    if isinstance(subs, dict) and subs.get("total", 0) > 30:
        puntos += 8
        hall.append(("bajo", f"Superficie amplia: {subs['total']} subdominios públicos."))
        recs.append("Revisa y retira los subdominios que ya no se usen.")
    if not recs:
        recs.append("Sin acciones urgentes. Repite la operación periódicamente.")
    return min(100, puntos), hall, sorted(set(recs), key=recs.index)


def _ips_de(r: dict[str, Any]) -> list[str]:
    ips = []
    dns_ = r.get("DNS")
    if isinstance(dns_, dict):
        ips += [x for x in dns_.get("A", []) if isinstance(x, str)]
    return ips[:3]


# ── operación ──────────────────────────────────────────────────────────────────


def consultas_dominio(dominio: str) -> dict[str, Consulta]:
    from .osint import certificados

    def subdominios(c):
        lista = set(F.seguro(certificados, dominio, c) or [])
        ht = F.seguro(F.hackertarget, c, dominio)
        lista |= set(ht if isinstance(ht, list) else [])
        ext = F.subdominios_externos(dominio)
        lista |= set(ext.get("subdominios", []))
        return {"total": len(lista), "lista": sorted(lista)[:300],
                "herramientas": ["crt.sh", "HackerTarget", *ext.get("herramientas", [])]}

    return {
        "DNS": lambda c: F.dns_completo(c, dominio),
        "Registro (RDAP)": lambda c: F.rdap(c, dominio),
        "Correo (SPF/DMARC)": lambda c: F.seguridad_correo(dominio, c),
        "Subdominios": subdominios,
        "Tecnologías web": lambda c: F.tecnologias(c, f"https://{dominio}/"),
        "Wayback Machine": lambda c: F.wayback(c, dominio),
        "urlscan.io": lambda c: F.urlscan(c, dominio),
        "AlienVault OTX": lambda c: F.otx(c, "dominio", dominio),
    }


def consultas_ip(ip: str, sufijo: str = "") -> dict[str, Consulta]:
    def inverso(_c):
        try:
            return {"nombre": socket.gethostbyaddr(ip)[0]}
        except OSError:
            return {}

    return {
        f"Geolocalización{sufijo}": lambda c: F.geo(c, ip),
        f"Shodan InternetDB{sufijo}": lambda c: F.internetdb(c, ip),
        f"RIPEstat{sufijo}": lambda c: F.ripe(c, ip),
        f"GreyNoise{sufijo}": lambda c: F.greynoise(c, ip),
        f"AlienVault OTX{sufijo}": lambda c: F.otx(c, "ip", ip),
        f"DNS inverso{sufijo}": inverso,
        f"Shodan{sufijo}": lambda c: F.shodan_completo(c, ip),
    }


def puntos_mapa(r: dict[str, Any]) -> list[dict]:
    puntos = []
    for nombre, d in r.items():
        if nombre.startswith("Geolocalización") and isinstance(d, dict) and d.get("lat"):
            puntos.append({"etiqueta": nombre, "lat": d["lat"], "lon": d["lon"],
                           "lugar": f"{d.get('city', '')}, {d.get('country', '')}"})
    return puntos


def _abrir(ej, ruta: Path | str) -> None:
    if ej.existe("xdg-open"):
        ej.run(["xdg-open", str(ruta)], check=False, fondo=True)


def registrar(app: typer.Typer) -> None:  # noqa: C901 (registro de todos los comandos)
    @app.command("operacion")
    def operacion(
        ctx: typer.Context,
        objetivo: str = typer.Argument(..., help="Dominio, IP pública o URL."),
        mapa: bool = typer.Option(False, "--mapa", help="Sitúa el objetivo en el Ojo de Dios."),
        abrir: bool = typer.Option(True, "--abrir/--no-abrir", help="Abre el dossier."),
        json_: bool = typer.Option(False, "--json"),
    ) -> None:
        """Operación completa: todas las fuentes a la vez, puntuación, dossier y mapa."""
        ej = ejecutor(ctx)
        try:
            tipo = tipo_objetivo(objetivo)
        except ValueError as exc:
            fallo(str(exc), 2)
        if tipo == "url":
            objetivo = (re.sub(r"^https?://", "", objetivo).split("/")[0]).split(":")[0]
            tipo = "ip" if re.fullmatch(r"[\d.]+", objetivo) else "dominio"
        if tipo == "ip" and not ipaddress.ip_address(objetivo).is_global:
            fallo("Esa IP es privada: usa `ultron radar` para tu red local.", 2)
        if ej.simular:
            mostrar("OPERACIÓN", {"objetivo": objetivo, "tipo": tipo, "simulación": True}, json_)
            return
        consultas = consultas_dominio(objetivo) if tipo == "dominio" else consultas_ip(objetivo)
        r = ejecutar_fuentes(consultas, objetivo, en_vivo=not json_)
        if tipo == "dominio":
            ips = _ips_de(r)
            extra: dict[str, Consulta] = {}
            for ip_ in ips:
                extra.update(consultas_ip(ip_, f" · {ip_}"))
            if extra:
                r.update(ejecutar_fuentes(extra, f"{objetivo} → {', '.join(ips)}",
                                          en_vivo=not json_))
        puntuacion, hallazgos, recs = evaluar_infra(r)
        datos = {"objetivo": objetivo, "tipo": tipo, "exposicion": puntuacion,
                 "hallazgos": [t for _n, t in hallazgos], "fuentes": r,
                 "mapa": puntos_mapa(r)}
        carpeta = guardar(objetivo, datos, ej)
        if json_:
            mostrar("OPERACIÓN", datos, True)
            return
        _resumen(objetivo, puntuacion, hallazgos, recs)
        if carpeta:
            html = dossier.generar(carpeta / "dossier.html", titulo="DOSSIER DE OPERACIÓN",
                                   objetivo=objetivo, tipo=tipo.upper(), puntuacion=puntuacion,
                                   hallazgos=hallazgos, recomendaciones=recs,
                                   secciones={k: v for k, v in r.items()
                                              if isinstance(v, dict)})
            pdf = dossier.a_pdf(html)
            interfaz().ok(f"Dossier: {pdf or html}")
            if abrir:
                _abrir(ej, pdf or html)
        if mapa and datos["mapa"]:
            from .ojo import objetivo as ojo_objetivo

            p = datos["mapa"][0]
            interfaz().info(f"Situando {objetivo} en el Ojo de Dios: {p['lugar']}")
            ojo_objetivo(ctx, f"{p['lat']},{p['lon']}")

    @app.command("url")
    def url(ctx: typer.Context, enlace: str = typer.Argument(..., help="Enlace sospechoso."),
            json_: bool = typer.Option(False, "--json")) -> None:
        """¿Es fiable este enlace? Redirecciones, señales de phishing y reputación."""
        if not re.match(r"^https?://", enlace, re.I):
            enlace = "https://" + enlace
        ej = ejecutor(ctx)
        if ej.simular:
            mostrar("ENLACE", {"url": enlace, "simulación": True}, json_)
            return
        host = re.sub(r"^https?://", "", enlace).split("/")[0].split(":")[0]
        r = ejecutar_fuentes({
            "Redirecciones": lambda c: F.redirecciones(c, enlace),
            "Registro (RDAP)": lambda c: F.rdap(c, ".".join(host.split(".")[-2:])),
            "AlienVault OTX": lambda c: F.otx(c, "url", enlace),
            "urlscan.io": lambda c: F.urlscan(c, host),
            "VirusTotal": lambda c: F.virustotal(c, enlace),
        }, host, en_vivo=not json_)
        senales = F.senales_url(enlace)
        destino = (r.get("Redirecciones") or {}).get("destino", "") if isinstance(
            r.get("Redirecciones"), dict) else ""
        if destino and destino != enlace:
            senales += [f"(destino) {s}" for s in F.senales_url(destino)]
        alta = (r.get("Registro (RDAP)") or {}).get("alta") if isinstance(
            r.get("Registro (RDAP)"), dict) else None
        if alta:
            try:
                dias = (datetime.now() - datetime.fromisoformat(alta)).days
                if dias < 60:
                    senales.append(f"dominio creado hace solo {dias} días")
            except ValueError:
                pass
        otx_ = r.get("AlienVault OTX")
        if isinstance(otx_, dict) and otx_.get("pulsos_de_amenaza"):
            senales.append(f"aparece en {otx_['pulsos_de_amenaza']} informes de amenazas")
        vt = r.get("VirusTotal")
        if isinstance(vt, dict) and vt.get("malicious"):
            senales.append(f"{vt['malicious']} antivirus la marcan como maliciosa")
        veredicto = ("PELIGROSO" if len(senales) >= 3 else
                     "SOSPECHOSO" if senales else "SIN SEÑALES DE RIESGO")
        datos = {"url": enlace, "veredicto": veredicto, "señales": senales,
                 "destino_final": destino, "fuentes": r}
        guardar(host, datos, ej)
        if json_:
            mostrar("ENLACE", datos, True)
            return
        t = interfaz()
        estilo = "error" if veredicto == "PELIGROSO" else ("aviso" if senales else "ok")
        cuerpo = Text(f"{veredicto}\n\n", style=f"bold {estilo}")
        for s in senales or ["Ninguna señal de phishing en la dirección ni en las fuentes."]:
            cuerpo.append(f" ▸ {s}\n")
        if destino:
            cuerpo.append(f"\nDestino real: {destino}", style="apagado")
        t.consola.print(t.panel(cuerpo, titulo="VEREDICTO DEL ENLACE", border_style=estilo))

    @app.command("imagen")
    def imagen(ctx: typer.Context,
               origen: str = typer.Argument(..., help="Foto local o URL de una imagen."),
               abrir: bool = typer.Option(False, "--abrir", help="Abre las búsquedas.")) -> None:
        """Metadatos y GPS de una foto, y búsqueda inversa en cuatro buscadores."""
        from .osint import metadatos

        ej = ejecutor(ctx)
        datos: dict[str, Any] = {"origen": origen}
        if re.match(r"^https?://", origen):
            datos["búsqueda inversa"] = F.busqueda_inversa(origen)
        else:
            ruta = Path(origen).expanduser()
            if not ruta.is_file():
                fallo("No encuentro esa imagen.", 2)
            datos["metadatos"] = F.seguro(metadatos, ruta)
            datos["búsqueda inversa"] = {
                "Google Lens (sube la foto)": "https://lens.google.com/",
                "Bing Visual (sube la foto)": "https://www.bing.com/visualsearch",
                "Yandex (sube la foto)": "https://yandex.com/images/",
                "TinEye (sube la foto)": "https://tineye.com/"}
        mostrar("IMAGEN", datos)
        if abrir and not ej.simular:
            for enlace in datos["búsqueda inversa"].values():
                _abrir(ej, enlace)

    @app.command("huella")
    def huella(
        ctx: typer.Context,
        correo: str = typer.Option("", "--correo", help="Correo de la persona."),
        alias: str = typer.Option("", "--alias", help="Nombre de usuario que usa."),
        nombre: str = typer.Option("", "--nombre", help="Nombre y apellidos."),
        fotos: list[Path] = typer.Option(None, "--foto", help="Fotos suyas (repetible)."),
        para: str = typer.Option("", "--para", help="Persona del informe (vacío = tú)."),
        autorizado: bool = typer.Option(False, "--autorizado",
                                        help="Confirma que la persona lo ha autorizado."),
    ) -> None:
        """Informe de huella digital de ti o de alguien que te lo ha pedido o autorizado."""
        ej = ejecutor(ctx)
        t = interfaz()
        if not (correo or alias or nombre or fotos):
            fallo("Indica al menos --correo, --alias, --nombre o --foto.", 2)
        persona = para.strip() or "yo"
        if persona.lower() not in {"yo", "mí", "mi"}:
            t.consola.print(t.panel(
                Text("Este informe reúne datos de una persona. Solo se hace si ELLA lo ha "
                     "pedido o autorizado antes. La confirmación queda registrada en el "
                     "informe.", style="aviso"), titulo="CONSENTIMIENTO", border_style="aviso"))
            if not autorizado and not typer.confirm(
                    f"¿{persona} te ha pedido o autorizado este informe?", default=False):
                fallo("Sin autorización no se hace el informe.", 1)
        if ej.simular:
            mostrar("HUELLA", {"persona": persona, "simulación": True})
            return
        consultas: dict[str, Consulta] = {}
        if correo:
            consultas["Filtraciones (XposedOrNot)"] = lambda c: F.xposedornot(c, correo)
            consultas["Filtraciones (HIBP)"] = lambda c: F.hibp(c, correo)
            consultas["Gravatar"] = lambda c: F.gravatar(c, correo)
        if alias:
            def perfiles(_c):
                from .osint import buscar_usuario

                sitios = json.loads((Path(__file__).with_name("datos") / "sitios.json")
                                    .read_text(encoding="utf-8"))

                async def todo():
                    async with httpx.AsyncClient(follow_redirects=False) as cl:
                        return await buscar_usuario(alias, sitios, cl)

                propios = asyncio.run(todo())
                externos = F.alias_externo(alias)
                vistos = {p["enlace"] for p in propios}
                propios += [p for p in externos.get("perfiles", []) if p["enlace"] not in vistos]
                return {"total": len(propios), "perfiles": propios,
                        "herramienta": externos.get("herramienta") or "Ultron"}
            consultas["Perfiles del alias"] = perfiles
        r = ejecutar_fuentes(consultas, persona) if consultas else {}
        if fotos:
            from .osint import metadatos

            r["Fotos"] = {f.name: F.seguro(metadatos, f) for f in fotos if f.is_file()}
        r["Búsquedas para revisar"] = F.busquedas(nombre, alias, correo)
        puntuacion, hallazgos, recs = evaluar_huella(r)
        datos = {"persona": persona,
                 "autorizacion": "propia" if persona == "yo" else "confirmada por el usuario",
                 "fecha": datetime.now().isoformat(timespec="seconds"),
                 "exposicion": puntuacion, "fuentes": r}
        carpeta = guardar(f"huella-{persona}", datos, ej)
        _resumen(persona, puntuacion, hallazgos, recs)
        if carpeta:
            html = dossier.generar(
                carpeta / "huella.html", titulo="INFORME DE HUELLA DIGITAL",
                objetivo=persona if persona != "yo" else "Informe personal", tipo="PERSONA",
                puntuacion=puntuacion, hallazgos=hallazgos, recomendaciones=recs,
                secciones={k: v for k, v in r.items() if isinstance(v, dict)},
                extra_meta={"AUTORIZACIÓN": "propia" if persona == "yo" else
                            f"confirmada {datetime.now():%d/%m/%Y %H:%M}"})
            pdf = dossier.a_pdf(html)
            t.ok(f"Informe listo para entregar: {pdf or html}")
            _abrir(ej, pdf or html)

    @app.command("fuentes")
    def fuentes_cmd() -> None:
        """Fuentes y herramientas OSINT conectadas, y cuáles faltan por instalar."""
        t = interfaz()
        tabla = t.tabla("Fuente", "Objetivo", "Qué aporta", "Estado",
                        titulo=f"{len(F.FUENTES)} FUENTES")
        for f in F.FUENTES:
            if f.clave:
                estado = Text("✔ clave", style="ok") if F.clave(f.clave) else \
                    Text(f"opcional: osint clave {f.clave}", style="apagado")
            else:
                estado = Text("✔ lista", style="ok")
            tabla.add_row(f.nombre, f.tipo, f.descripcion, estado)
        t.consola.print(tabla)
        tabla = t.tabla("Herramienta", "Qué aporta", "Estado",
                        titulo=f"{len(F.HERRAMIENTAS)} HERRAMIENTAS EXTERNAS")
        for h in F.HERRAMIENTAS:
            tabla.add_row(h.programa, h.descripcion,
                          Text("✔ instalada", style="ok") if F.instalada(h.programa)
                          else Text(h.instalar, style="apagado"))
        t.consola.print(tabla)

    @app.command("clave")
    def clave_cmd(servicio: str = typer.Argument(..., help="shodan, virustotal o hibp."),
                  valor: str = typer.Argument(..., help="La clave de la API.")) -> None:
        """Guarda la clave opcional de un servicio (se guarda con permisos 600)."""
        if servicio not in {"shodan", "virustotal", "hibp"}:
            fallo("Servicios con clave: shodan, virustotal, hibp.", 2)
        config.fijar("osint_claves", servicio, valor.strip())
        interfaz().ok(f"Clave de {servicio} guardada.")


def evaluar_huella(r: dict[str, Any]) -> tuple[int, list[tuple[str, str]], list[str]]:
    puntos, hall, recs = 0, [], []
    filtraciones: list[dict] = []
    for clave_ in ("Filtraciones (XposedOrNot)", "Filtraciones (HIBP)"):
        d = r.get(clave_)
        if isinstance(d, dict):
            filtraciones += d.get("filtraciones", [])
    nombres = {str(f.get("nombre")) for f in filtraciones}
    if nombres:
        puntos += min(50, 10 * len(nombres))
        hall.append(("alto", f"El correo aparece en {len(nombres)} filtraciones: "
                             f"{', '.join(sorted(nombres)[:6])}"))
        recs += ["Cambia la contraseña de esas webs y no la repitas en ninguna otra.",
                 "Activa la verificación en dos pasos en el correo y las redes.",
                 "Usa un gestor de contraseñas (Bitwarden, KeePassXC)."]
    perfiles = r.get("Perfiles del alias")
    if isinstance(perfiles, dict) and perfiles.get("total"):
        n = perfiles["total"]
        puntos += min(25, n)
        hall.append(("medio" if n > 10 else "bajo", f"El alias aparece en {n} webs públicas."))
        recs.append("Cierra las cuentas que ya no uses y revisa la privacidad de las demás.")
    grav = r.get("Gravatar")
    if isinstance(grav, dict) and grav.get("perfil_publico"):
        puntos += 5
        hall.append(("bajo", "El correo tiene un perfil público en Gravatar."))
    fotos = r.get("Fotos")
    if isinstance(fotos, dict):
        con_gps = [n for n, d in fotos.items() if "GPS" in json.dumps(d)]
        if con_gps:
            puntos += 20
            hall.append(("alto", f"Fotos con ubicación GPS: {', '.join(con_gps)}"))
            recs.append("Quita los metadatos antes de compartir fotos (ultron limpiar-meta).")
    recs.append("Revisa los enlaces de «Búsquedas para revisar» y pide la retirada de lo que "
                "no quieras que se vea (Google: «Resultados sobre ti»).")
    return min(100, puntos), hall, list(dict.fromkeys(recs))


def _resumen(objetivo: str, puntuacion: int, hallazgos: list[tuple[str, str]],
             recs: list[str]) -> None:
    t = interfaz()
    estilo = "error" if puntuacion >= 60 else ("aviso" if puntuacion >= 30 else "ok")
    barra = "█" * (puntuacion // 5) + "░" * (20 - puntuacion // 5)
    cuerpo = Text()
    cuerpo.append(f"EXPOSICIÓN  {barra}  {puntuacion}/100\n\n", style=f"bold {estilo}")
    for nivel, texto in hallazgos or [("bajo", "Sin hallazgos relevantes.")]:
        cuerpo.append({"alto": " ▲ ", "medio": " ■ ", "bajo": " ● "}[nivel],
                      style={"alto": "error", "medio": "aviso", "bajo": "acento"}[nivel])
        cuerpo.append(texto + "\n")
    cuerpo.append("\nRECOMENDACIONES\n", style="bold acento")
    for r in recs[:6]:
        cuerpo.append(f" ✔ {r}\n")
    t.consola.print(t.panel(cuerpo, titulo=f"VALORACIÓN · {objetivo}", border_style=estilo))


def ruta_operaciones() -> Path:
    return rutas.datos() / "operaciones"
