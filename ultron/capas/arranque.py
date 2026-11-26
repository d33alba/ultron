"""Capa arranque: pantalla de carga (Plymouth), GRUB y fondo de la pantalla de inicio (GDM).

Necesita sudo y tarda (update-initramfs), así que está desactivada por defecto:
se activa con `ultron entrar <modo> --arranque` o con [arranque] activar = true en config.
"""

from __future__ import annotations

import os
from pathlib import Path

from ultron.capas import comun as C
from ultron.capas import estilos
from ultron.capas.base import Capa, registrar_capa
from ultron.nucleo import config, rutas
from ultron.ui.tema import cargar_tema

PLYMOUTH = Path("/usr/share/plymouth/themes")
ALTERNATIVA = "default.plymouth"
ENLACE_ALT = PLYMOUTH / "default.plymouth"
GRUB_D = Path("/etc/default/grub.d/99-ultron.cfg")
GRUB_IMG = Path("/boot/grub")
GDM_DB = Path("/etc/dconf/db/gdm.d/99-ultron")
GDM_PERFIL = Path("/etc/dconf/profile/gdm")
FONDOS = Path("/usr/share/backgrounds")


def script_plymouth(p: dict[str, str]) -> str:
    """Script de Plymouth: logo con pulso, barra de progreso y petición de contraseña (LUKS)."""
    fr, fg, fb = (c / 255 for c in C.hex_a_rgb(p.get("fondo", "#000000")))
    ar, ag, ab = (c / 255 for c in C.hex_a_rgb(C.oscurecer(p.get("fondo", "#000000"), 0.5)))
    pr, pg, pb = (c / 255 for c in C.hex_a_rgb(p.get("primario", "#ffffff")))
    return f"""// Generado por Ultron
Window.SetBackgroundTopColor({fr:.3f}, {fg:.3f}, {fb:.3f});
Window.SetBackgroundBottomColor({ar:.3f}, {ag:.3f}, {ab:.3f});

logo.image = Image("logo.png");
escala = Math.Min(Window.GetWidth() * 0.35 / logo.image.GetWidth(), 1);
logo.image = logo.image.Scale(logo.image.GetWidth() * escala, logo.image.GetHeight() * escala);
logo.sprite = Sprite(logo.image);
logo.sprite.SetX(Window.GetWidth() / 2 - logo.image.GetWidth() / 2);
logo.sprite.SetY(Window.GetHeight() / 2 - logo.image.GetHeight() / 2);

barra.ancho = Window.GetWidth() * 0.3;
barra.fondo = Image("barra.png").Scale(barra.ancho, 4);
barra.sprite = Sprite(barra.fondo);
barra.sprite.SetX(Window.GetWidth() / 2 - barra.ancho / 2);
barra.sprite.SetY(Window.GetHeight() * 0.75);
barra.sprite.SetOpacity(0.25);
progreso.sprite = Sprite();
progreso.sprite.SetX(Window.GetWidth() / 2 - barra.ancho / 2);
progreso.sprite.SetY(Window.GetHeight() * 0.75);

tiempo = 0;
fun refrescar() {{
  tiempo++;
  logo.sprite.SetOpacity(0.65 + 0.35 * Math.Sin(tiempo / 18));
}}
Plymouth.SetRefreshFunction(refrescar);

fun avance(duracion, fraccion) {{
  ancho = Math.Int(barra.ancho * fraccion);
  if (ancho > 0) progreso.sprite.SetImage(Image("barra.png").Scale(ancho, 4));
}}
Plymouth.SetBootProgressFunction(avance);

// Contraseña de disco cifrado: imprescindible para no bloquear el arranque.
mensaje.sprite = Sprite();
fun pedir_clave(texto, puntos) {{
  linea = texto + "  ";
  for (i = 0; i < puntos; i++) linea = linea + "*";
  texto_img = Image.Text(linea, {pr:.3f}, {pg:.3f}, {pb:.3f});
  mensaje.sprite.SetImage(texto_img);
  mensaje.sprite.SetX(Window.GetWidth() / 2 - texto_img.GetWidth() / 2);
  mensaje.sprite.SetY(Window.GetHeight() * 0.65);
  mensaje.sprite.SetOpacity(1);
}}
Plymouth.SetDisplayPasswordFunction(pedir_clave);
fun normal() {{ mensaje.sprite.SetOpacity(0); }}
Plymouth.SetDisplayNormalFunction(normal);
fun pedir_texto(texto, entrada) {{ pedir_clave(texto + " " + entrada, 0); }}
Plymouth.SetDisplayQuestionFunction(pedir_texto);
fun mensaje_sistema(texto) {{ pedir_clave(texto, 0); }}
Plymouth.SetMessageFunction(mensaje_sistema);
"""


def archivo_plymouth(nombre: str, dir_tema: Path) -> str:
    return (
        "[Plymouth Theme]\n"
        f"Name={nombre}\nDescription=Tema de arranque de Ultron\nModuleName=script\n\n"
        f"[script]\nImageDir={dir_tema}\nScriptFile={dir_tema}/{nombre}.script\n"
    )


def grub_cfg(imagen: Path, p: dict[str, str]) -> str:
    return (
        "# Generado por Ultron. Se borra al salir del modo.\n"
        f'GRUB_BACKGROUND="{imagen}"\n'
        'GRUB_COLOR_NORMAL="light-gray/black"\n'
        'GRUB_COLOR_HIGHLIGHT="white/blue"\n'
        "GRUB_TIMEOUT_STYLE=menu\n"
    )


def gdm_db(imagen: Path, p: dict[str, str]) -> str:
    return (
        "# Generado por Ultron\n[org/gnome/desktop/background]\n"
        f"picture-uri='file://{imagen}'\npicture-uri-dark='file://{imagen}'\n"
        f"primary-color='{p.get('fondo', '#000000')}'\n\n"
        "[org/gnome/desktop/interface]\ncolor-scheme='prefer-dark'\n"
    )


PERFIL_GDM = "user-db:user\nsystem-db:gdm\nfile-db:/usr/share/gdm/greeter-dconf-defaults\n"


def activada(cfg: dict) -> bool:
    return bool(os.environ.get("ULTRON_ARRANQUE") or cfg.get("activar")
                or config.obtener("arranque", "activar", False))


@registrar_capa
class CapaArranque(Capa):
    nombre = "arranque"
    orden = 95
    requiere_sudo = True
    descripcion = "Arranque: Plymouth, GRUB y pantalla de inicio de sesión (sudo)"

    def disponible(self) -> tuple[bool, str]:
        cfg = self.ctx.modo.capas.get("arranque", {})
        if not activada(cfg):
            return False, "desactivada (usa --arranque para cambiar también el arranque)"
        if not self.ej.simular and not PLYMOUTH.exists():
            return False, "no hay Plymouth en este sistema"
        return True, ""

    @property
    def nombre_tema(self) -> str:
        return f"ultron-{self.ctx.modo.id}"

    def capturar(self, cfg: dict) -> dict:
        actual = None
        if self.ej.existe("update-alternatives"):
            r = self.ej.leer(["update-alternatives", "--query", ALTERNATIVA])
            for linea in r.salida.splitlines():
                if linea.startswith("Value:"):
                    actual = linea.split(":", 1)[1].strip()
        return {"plymouth": actual, "gdm_perfil_existia": GDM_PERFIL.exists(),
                "partes": list(cfg.get("partes") or ["plymouth", "grub", "gdm"])}

    def _imagen(self, cfg: dict, clave: str, nombre: str) -> Path:
        ruta = self.ctx.recurso(cfg.get(clave) or "tema/fondo.png")
        if ruta.exists():
            return ruta
        destino = rutas.cache() / "arranque" / f"{self.ctx.modo.id}-{nombre}.png"
        if not destino.exists() and not self.ej.simular:
            estilos.fondo_respaldo(cargar_tema(self.ctx.modo.id).paleta, destino,
                                   texto=f"ULTRON · {self.ctx.modo.nombre}")
        return destino

    def _barra(self, p: dict) -> Path:
        destino = rutas.cache() / "arranque" / f"{self.ctx.modo.id}-barra.png"
        if not self.ej.simular:
            from PIL import Image

            destino.parent.mkdir(parents=True, exist_ok=True)
            Image.new("RGB", (8, 4), C.hex_a_rgb(p.get("primario", "#ffffff"))).save(destino)
        return destino

    def aplicar(self, cfg: dict) -> None:
        p = cargar_tema(self.ctx.modo.id).paleta
        partes = cfg.get("partes") or ["plymouth", "grub", "gdm"]
        if "plymouth" in partes:
            self._plymouth(cfg, p)
        if "grub" in partes and self.ej.existe("update-grub"):
            img = GRUB_IMG / f"{self.nombre_tema}.png"
            self.ej.copiar(self._imagen(cfg, "fondo_grub", "grub"), img, sudo=True)
            self.ej.run(["mkdir", "-p", str(GRUB_D.parent)], sudo=True)
            self.ej.escribir(GRUB_D, grub_cfg(img, p), sudo=True)
            self.ej.run(["update-grub"], sudo=True, timeout=300)
        if "gdm" in partes and (Path("/etc/dconf").exists() or self.ej.simular):
            img = FONDOS / f"{self.nombre_tema}.png"
            self.ej.copiar(self._imagen(cfg, "fondo_gdm", "gdm"), img, sudo=True)
            if not GDM_PERFIL.exists():
                self.ej.escribir(GDM_PERFIL, PERFIL_GDM, sudo=True)
            self.ej.run(["mkdir", "-p", str(GDM_DB.parent)], sudo=True)
            self.ej.escribir(GDM_DB, gdm_db(img, p), sudo=True)
            self.ej.run(["dconf", "update"], sudo=True)

    def _plymouth(self, cfg: dict, p: dict) -> None:
        d = PLYMOUTH / self.nombre_tema
        self.ej.run(["mkdir", "-p", str(d)], sudo=True)
        logo = self.ctx.recurso(cfg.get("logo", "tema/arranque/logo.png"))
        if not logo.exists():
            logo = self._imagen({}, "logo", "logo")
        self.ej.copiar(logo, d / "logo.png", sudo=True)
        self.ej.copiar(self._barra(p), d / "barra.png", sudo=True)
        self.ej.escribir(d / f"{self.nombre_tema}.script", script_plymouth(p), sudo=True)
        archivo = d / f"{self.nombre_tema}.plymouth"
        self.ej.escribir(archivo, archivo_plymouth(self.nombre_tema, d), sudo=True)
        self.ej.run(["update-alternatives", "--install", str(ENLACE_ALT), ALTERNATIVA,
                     str(archivo), "200"], sudo=True)
        self.ej.run(["update-alternatives", "--set", ALTERNATIVA, str(archivo)], sudo=True)
        self.ej.run(["update-initramfs", "-u"], sudo=True, timeout=600)

    def restaurar(self, previo: dict) -> None:
        partes = previo.get("partes") or ["plymouth", "grub", "gdm"]
        if "plymouth" in partes:
            d = PLYMOUTH / self.nombre_tema
            archivo = d / f"{self.nombre_tema}.plymouth"
            if previo.get("plymouth") and previo["plymouth"] != str(archivo):
                self.ej.run(["update-alternatives", "--set", ALTERNATIVA, previo["plymouth"]],
                            sudo=True, check=False)
            self.ej.run(["update-alternatives", "--remove", ALTERNATIVA, str(archivo)],
                        sudo=True, check=False)
            self.ej.borrar(d, sudo=True)
            self.ej.run(["update-initramfs", "-u"], sudo=True, timeout=600, check=False)
        if "grub" in partes:
            self.ej.borrar(GRUB_D, sudo=True)
            self.ej.borrar(GRUB_IMG / f"{self.nombre_tema}.png", sudo=True)
            if self.ej.existe("update-grub"):
                self.ej.run(["update-grub"], sudo=True, timeout=300, check=False)
        if "gdm" in partes:
            self.ej.borrar(GDM_DB, sudo=True)
            self.ej.borrar(FONDOS / f"{self.nombre_tema}.png", sudo=True)
            if not previo.get("gdm_perfil_existia"):
                self.ej.borrar(GDM_PERFIL, sudo=True)
            self.ej.run(["dconf", "update"], sudo=True, check=False)
