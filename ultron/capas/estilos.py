"""Generadores de CSS (GTK 3, GTK 4/libadwaita, GNOME Shell) y de un fondo de respaldo."""

from __future__ import annotations

from pathlib import Path

from ultron.capas import comun as C


def _colores(p: dict[str, str], oscuro: bool = True) -> dict[str, str]:
    fondo = p.get("fondo", "#202020" if oscuro else "#fafafa")
    texto = p.get("texto", "#eeeeee" if oscuro else "#202020")
    primario = p.get("bandera") or p.get("primario", "#3584e4")
    return {
        "accent": primario,
        "accent_fg": "#ffffff",
        "window_bg": fondo,
        "window_fg": texto,
        "view_bg": C.oscurecer(fondo, 0.15) if oscuro else "#ffffff",
        "headerbar_bg": C.mezclar(fondo, primario, 0.18),
        "headerbar_fg": texto,
        "sidebar_bg": C.mezclar(fondo, primario, 0.08),
        "card_bg": C.aclarar(fondo, 0.06),
        "popover_bg": C.aclarar(fondo, 0.04),
        "dialog_bg": C.aclarar(fondo, 0.03),
        "borde": C.mezclar(fondo, primario, 0.45),
        "acento2": p.get("acento", primario),
        "error": p.get("error", "#e01b24"),
        "aviso": p.get("aviso", "#e5a50a"),
        "ok": p.get("ok", "#2ec27e"),
    }


def css_gtk4(p: dict[str, str], oscuro: bool = True) -> str:
    c = _colores(p, oscuro)
    hover = f"button:hover {{ border-color: {c['acento2']}; }}\n" if (
        p.get("primario") == "#FF00E6"
    ) else ""
    return f"""/* Generado por Ultron. Se restaura al salir del modo. */
@define-color accent_color {c['acento2']};
@define-color accent_bg_color {c['accent']};
@define-color accent_fg_color {c['accent_fg']};
@define-color window_bg_color {c['window_bg']};
@define-color window_fg_color {c['window_fg']};
@define-color view_bg_color {c['view_bg']};
@define-color view_fg_color {c['window_fg']};
@define-color headerbar_bg_color {c['headerbar_bg']};
@define-color headerbar_fg_color {c['headerbar_fg']};
@define-color headerbar_backdrop_color {c['window_bg']};
@define-color sidebar_bg_color {c['sidebar_bg']};
@define-color sidebar_fg_color {c['window_fg']};
@define-color card_bg_color {c['card_bg']};
@define-color card_fg_color {c['window_fg']};
@define-color popover_bg_color {c['popover_bg']};
@define-color popover_fg_color {c['window_fg']};
@define-color dialog_bg_color {c['dialog_bg']};
@define-color dialog_fg_color {c['window_fg']};
@define-color destructive_bg_color {c['error']};
@define-color warning_bg_color {c['aviso']};
@define-color success_bg_color {c['ok']};

headerbar {{ border-bottom: 1px solid {c['borde']}; }}
button.suggested-action {{ background-color: {c['accent']}; color: {c['accent_fg']}; }}
{hover}selection, *:selected {{ background-color: alpha({c['accent']}, 0.55); }}
"""


def css_gtk3(p: dict[str, str], oscuro: bool = True) -> str:
    c = _colores(p, oscuro)
    base = "Adwaita/gtk-contained-dark.css" if oscuro else "Adwaita/gtk-contained.css"
    hover = f"button:hover {{ border-color: {c['acento2']}; }}\n" if (
        p.get("primario") == "#FF00E6"
    ) else ""
    return f"""/* Generado por Ultron. */
@import url("resource:///org/gtk/libgtk/theme/{base}");
@define-color theme_bg_color {c['window_bg']};
@define-color theme_fg_color {c['window_fg']};
@define-color theme_base_color {c['view_bg']};
@define-color theme_text_color {c['window_fg']};
@define-color theme_selected_bg_color {c['accent']};
@define-color theme_selected_fg_color {c['accent_fg']};
@define-color borders {c['borde']};

window, .background {{ background-color: {c['window_bg']}; color: {c['window_fg']}; }}
headerbar, .titlebar {{ background: {c['headerbar_bg']}; color: {c['headerbar_fg']};
  border-bottom: 1px solid {c['borde']}; }}
.sidebar, placessidebar {{ background-color: {c['sidebar_bg']}; }}
{hover}*:selected, selection {{ background-color: {c['accent']}; color: {c['accent_fg']}; }}
button.suggested-action {{ background: {c['accent']}; color: {c['accent_fg']}; }}
"""


def css_shell(p: dict[str, str], oscuro: bool = True, brillo: bool = False) -> str:
    c = _colores(p, oscuro)
    panel = C.oscurecer(c["window_bg"], 0.2)
    neon = brillo and p.get("primario") == "#FF00E6"
    if neon:
        panel = "rgba(0, 0, 0, 0.78)"
    hover = c['acento2'] if neon else c['accent']
    resplandor = f"box-shadow: 0 0 12px {c['acento2']};" if brillo else ""
    degradado = (
        f"#panel {{ background-gradient-direction: vertical; "
        f"background-gradient-start: {panel}; "
        f"background-gradient-end: {c['headerbar_bg']}; "
        f"box-shadow: inset 0 -2px 4px {c['acento2']}; }}\n" if neon else ""
    )
    return f"""/* Tema de GNOME Shell generado por Ultron. */
@import url("resource:///org/gnome/shell/theme/gnome-shell.css");
@import url("resource:///org/gnome/shell/theme/gnome-shell-dark.css");

#panel {{ background-color: {panel}; border-bottom: 2px solid {c['accent']}; {resplandor} }}
{degradado}#panel .panel-button {{ color: {c['window_fg']}; }}
#panel .panel-button:hover, #panel .panel-button:active {{
  background-color: alpha({hover}, 0.35); color: #ffffff; }}
.popup-menu-content, .candidate-popup-content {{
  background-color: {c['popover_bg']}; color: {c['window_fg']};
  border: 1px solid {c['borde']}; {resplandor} }}
.popup-menu-item:hover, .popup-menu-item:focus {{ background-color: alpha({hover}, 0.4); }}
.quick-settings {{ background-color: {c['popover_bg']}; border: 1px solid {c['borde']}; }}
.quick-toggle:checked {{ background-color: {c['accent']}; color: {c['accent_fg']}; }}
#dash .dash-background {{ background-color: alpha({c['window_bg']}, 0.85);
  border: 1px solid {c['borde']}; }}
.notification-banner, .message {{ background-color: {c['card_bg']}; color: {c['window_fg']}; }}
.osd-window {{ background-color: {c['popover_bg']}; color: {c['window_fg']};
  border: 1px solid {c['accent']}; }}
.search-entry {{ border: 1px solid {c['accent']}; }}
.workspace-thumbnail-indicator {{ border-color: {c['accent']}; }}
"""


def index_theme(nombre: str) -> str:
    return (
        "[Desktop Entry]\nType=X-GNOME-Metatheme\n"
        f"Name={nombre}\nComment=Tema generado por Ultron\nEncoding=UTF-8\n\n"
        f"[X-GNOME-Metatheme]\nGtkTheme={nombre}\n"
    )


def fondo_respaldo(p: dict[str, str], destino: Path, ancho: int = 1920, alto: int = 1080,
                   texto: str = "ULTRON") -> Path:
    """Fondo con degradado de la paleta y el nombre del modo (si el modo no trae uno)."""
    from PIL import Image, ImageDraw, ImageFont

    a = C.hex_a_rgb(p.get("fondo", "#101010"))
    b = C.hex_a_rgb(C.mezclar(p.get("fondo", "#101010"), p.get("primario", "#3366cc"), 0.45))
    img = Image.new("RGB", (ancho, alto))
    dibujo = ImageDraw.Draw(img)
    for y in range(alto):
        t = y / max(1, alto - 1)
        dibujo.line([(0, y), (ancho, y)], fill=tuple(round(a[i] + (b[i] - a[i]) * t)
                                                     for i in range(3)))
    try:
        fuente = ImageFont.truetype("DejaVuSans-Bold.ttf", alto // 10)
    except OSError:
        fuente = ImageFont.load_default()
    caja = dibujo.textbbox((0, 0), texto, font=fuente)
    x = (ancho - (caja[2] - caja[0])) // 2
    y = (alto - (caja[3] - caja[1])) // 2
    dibujo.text((x, y), texto, font=fuente, fill=C.hex_a_rgb(p.get("primario", "#ffffff")))
    destino.parent.mkdir(parents=True, exist_ok=True)
    img.save(destino)
    return destino
