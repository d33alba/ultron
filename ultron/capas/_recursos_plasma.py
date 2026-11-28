"""Recursos de Plasma generados a partir de la identidad de cada modo."""

from __future__ import annotations

import json

from ultron.capas.comun import hex_a_rgb, paleta_terminal

MENU = "kickoff"
TAREAS = "icontasks"
RELOJ = "digitalclock"
BANDEJA = "systemtray"
MEDIDORES = ("systemmonitor.cpu", "systemmonitor.net")
PANELES = {
    "gaming": [
        ("top", 28, False, (MENU, "appmenu", "panelspacer", *MEDIDORES, BANDEJA, RELOJ)),
        ("bottom", 62, True, (TAREAS,)),
    ],
    "focus": [("bottom", 30, True, (MENU, TAREAS, RELOJ))],
    "netanyahu": [("top", 42, False, (MENU, TAREAS, *MEDIDORES, BANDEJA, RELOJ))],
    "presentacion": [("left", 44, True, (MENU, TAREAS))],
    "fantasma": [("right", 32, True, (MENU, TAREAS, BANDEJA))],
}


def layout(modo: str) -> str:
    paneles = json.dumps(PANELES[modo])
    ocultar = json.dumps(modo in {"focus", "presentacion", "fantasma"})
    dock = json.dumps(modo == "gaming")
    return f"""
var anteriores = panels();
var definiciones = {paneles};
for (var i = 0; i < definiciones.length; i++) {{
    var d = definiciones[i];
    var panel = new Panel;
    panel.location = d[0];
    panel.height = d[1];
    panel.hiding = {ocultar} ? "autohide" : "none";
    if (d[2]) {{
        panel.alignment = "center";
        if (typeof panel.lengthMode !== "undefined") {{
            panel.lengthMode = "fit";
            panel.floating = true;
        }} else {{
            panel.minimumLength = 160;
            panel.maximumLength = 480;
            panel.length = 360;
            var rc = ConfigFile("plasmashellrc");
            rc.group = "PlasmaViews";
            var vista = ConfigFile(rc, "Panel " + panel.id);
            vista.writeEntry("floating", 1);
        }}
    }}
    for (var j = 0; j < d[3].length; j++) {{
        var widget = panel.addWidget("org.kde.plasma." + d[3][j]);
        if ({dock} && widget && d[0] === "bottom" && d[3][j] === "icontasks") {{
            widget.currentConfigGroup = ["General"];
            widget.writeConfig("launchers", "preferred://browser,preferred://filemanager,"
                + "applications:org.kde.konsole.desktop");
        }}
    }}
}}
for (var k = 0; k < anteriores.length; k++) anteriores[k].remove();
"""


def splash(nombre: str, lema: str, p: dict, duracion: int) -> str:
    return f"""import QtQuick 2.15
Rectangle {{
    id: pantalla
    property int stage: 0
    color: "{p['fondo']}"
    Column {{
        id: contenido
        anchors.centerIn: parent
        spacing: 18
        opacity: 0
        Text {{
            anchors.horizontalCenter: parent.horizontalCenter
            text: {json.dumps("◆  ULTRON  /  " + nombre)}
            color: "{p['acento']}"
            font.pixelSize: Math.min(58, pantalla.width / 22)
            font.letterSpacing: 4
            font.bold: true
        }}
        Text {{
            anchors.horizontalCenter: parent.horizontalCenter
            text: {json.dumps(lema)}
            color: "{p['texto']}"
            font.pixelSize: 20
        }}
        Rectangle {{
            anchors.horizontalCenter: parent.horizontalCenter
            width: Math.min(320, pantalla.width / 2)
            height: 3
            color: "{p['apagado']}"
            Rectangle {{
                height: parent.height
                width: parent.width * Math.min(1, (pantalla.stage + 1) / 7)
                color: "{p['acento']}"
                Behavior on width {{ NumberAnimation {{ duration: {duracion} }} }}
            }}
        }}
    }}
    NumberAnimation {{
        target: contenido
        property: "opacity"
        to: 1
        duration: {duracion}
        running: true
    }}
}}
"""


def marco(prefijo: str, fondo: str, acento: str, opacidad: float, radio: int) -> str:
    piezas = [(0, 0, "topleft"), (1, 0, "top"), (2, 0, "topright"),
              (0, 1, "left"), (1, 1, "center"), (2, 1, "right"),
              (0, 2, "bottomleft"), (1, 2, "bottom"), (2, 2, "bottomright")]
    formas = {
        "topleft": f"M0 20 V{radio} Q0 0 {radio} 0 H20 V20 Z",
        "topright": f"M0 0 H{20-radio} Q20 0 20 {radio} V20 H0 Z",
        "bottomleft": f"M0 0 H20 V20 H{radio} Q0 20 0 {20-radio} Z",
        "bottomright": f"M0 0 H20 V{20-radio} Q20 20 {20-radio} 20 H0 Z",
    }
    bordes = {
        "topleft": f"M1 20 V{radio} Q1 1 {radio} 1 H20",
        "topright": f"M0 1 H{20-radio} Q19 1 19 {radio} V20",
        "bottomleft": f"M1 0 V{20-radio} Q1 19 {radio} 19 H20",
        "bottomright": f"M0 19 H{20-radio} Q19 19 19 {20-radio} V0",
        "top": "M0 1 H20", "bottom": "M0 19 H20", "left": "M1 0 V20", "right": "M19 0 V20",
    }
    return "".join(
        f'<g id="{prefijo}{lado}" transform="translate({x*20},{y*20})">'
        f'<path d="{formas.get(lado, "M0 0 H20 V20 H0 Z")}" fill="{fondo}" '
        f'fill-opacity="{opacidad}"/><path d="{bordes.get(lado, "")}" fill="none" '
        f'stroke="{acento}"/></g>'
        for x, y, lado in piezas
    )


def svg(contenido: str, ancho: int = 60, alto: int = 60) -> str:
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{ancho}" height="{alto}">'
            f'{contenido}</svg>')


def botones(p: dict) -> dict[str, str]:
    simbolos = {"close": "M5 5l8 8m0-8-8 8", "minimize": "M5 11h8",
                "maximize": "M5 5h8v8H5z", "restore": "M7 5h6v6M5 7h6v6H5z"}
    return {
        f"{tipo}.svg": svg("".join(
            f'<g id="{estado}" transform="translate({18*i} 0)">'
            f'<rect width="18" height="18" rx="8" fill="{color}"/>'
            f'<path d="{trazo}" fill="none" stroke="{p["fondo"]}" stroke-width="1.5"/></g>'
            for i, (estado, color) in enumerate(
                (("active", p["acento"]), ("inactive", p["apagado"]), ("hover", p["texto"]))
            )
        ), 54, 18)
        for tipo, trazo in simbolos.items()
    }


def metadatos(identificador: str) -> str:
    return json.dumps({"KPlugin": {
        "Id": identificador, "Name": identificador, "Version": "1.0", "License": "MIT",
    }, "X-Plasma-API-Minimum-Version": "6.0"}, indent=2)


def colores(p: dict) -> dict[str, dict[str, str]]:
    def rgb(clave: str) -> str:
        return ",".join(map(str, hex_a_rgb(p[clave])))

    return {
        f"Colors:{grupo}": {"BackgroundNormal": rgb(fondo), "ForegroundNormal": rgb("texto"),
                            "ForegroundInactive": rgb("texto"),
                            "DecorationFocus": rgb("acento"), "DecorationHover": rgb("acento")}
        for grupo, fondo in (("Window", "fondo"), ("View", "fondo"), ("Button", "fondo"),
                             ("Tooltip", "fondo"), ("Selection", "primario"),
                             ("Header", "fondo"))
    }


def ini(grupos: dict[str, dict[str, str]]) -> str:
    return "".join(f"[{grupo}]\n" + "".join(f"{k}={v}\n" for k, v in claves.items())
                   + "\n" for grupo, claves in grupos.items())


def konsole(nombre: str, p: dict, fuente: str, opacidad: float) -> dict[str, str]:
    ansi = paleta_terminal(p)
    colores_perfil = {f"Color{i}": ansi[i] for i in range(8)}
    colores_perfil.update({f"Color{i}Intense": ansi[i + 8] for i in range(8)})
    colores_perfil.update(Background=p["fondo"], Foreground=p["texto"])
    return {
        f"{nombre}.profile": ini({
            "General": {"Name": nombre, "Parent": "FALLBACK/"},
            "Appearance": {"ColorScheme": nombre, "Font": fuente},
        }),
        f"{nombre}.colorscheme": ini({
            "General": {"Description": nombre, "Opacity": str(opacidad),
                        "Blur": str(opacidad < 1).lower()},
            **{k: {"Color": ",".join(map(str, hex_a_rgb(v)))}
               for k, v in colores_perfil.items()},
        }),
    }
