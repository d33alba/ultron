"""`ultron musica …` y `ultron tema importar`."""

from __future__ import annotations

import shutil
from pathlib import Path

import typer

from ultron.capas import sonido
from ultron.nucleo import estado, registro
from ultron.nucleo.ejecutor import Ejecutor
from ultron.ui import tema

app = typer.Typer()
musica = typer.Typer(help="Música del modo: importar, silenciar, reproducir.", no_args_is_help=True)
tema_app = typer.Typer(help="Recursos del tema de un modo.", no_args_is_help=True)
app.add_typer(musica, name="musica")
app.add_typer(tema_app, name="tema")


def _modo(id_modo: str | None):
    id_modo = id_modo or estado.modo_activo() or "netanyahu"
    return registro.obtener(id_modo)


def _es_url(texto: str) -> bool:
    return texto.startswith(("http://", "https://"))


def comando_importar(origen: str, destino: Path, inicio: str | None, fin: str | None) -> list[str]:
    """Comando para traer el audio: yt-dlp si es una URL, ffmpeg si es un archivo."""
    if _es_url(origen):
        cmd = ["yt-dlp", "-x", "--audio-format", "mp3", "--no-playlist",
               "-o", str(destino.with_suffix(".%(ext)s"))]
        if inicio or fin:
            cmd += ["--download-sections", f"*{inicio or '0'}-{fin or 'inf'}"]
        return [*cmd, origen]
    cmd = ["ffmpeg", "-y", "-i", origen]
    if inicio:
        cmd += ["-ss", inicio]
    if fin:
        cmd += ["-to", fin]
    return [*cmd, "-vn", "-codec:a", "libmp3lame", "-q:a", "2", str(destino)]


@musica.command("importar")
def cmd_importar(
    origen: str = typer.Argument(..., help="URL o archivo de audio."),
    modo: str = typer.Option(None, "--modo", "-m", help="Modo (por defecto, el activo)."),
    inicio: str = typer.Option(None, "--inicio", help="Recortar desde (p. ej. 0:30)."),
    fin: str = typer.Option(None, "--fin", help="Recortar hasta (p. ej. 2:00)."),
) -> None:
    """Guarda la música de un modo a partir de una URL o de un archivo."""
    t = tema.actual()
    m = _modo(modo)
    destino = m.dir_usuario() / "tema" / "musica.mp3"
    destino.parent.mkdir(parents=True, exist_ok=True)
    ej = Ejecutor(consola=t.consola)
    programa = "yt-dlp" if _es_url(origen) else "ffmpeg"
    if not ej.existe(programa):
        t.error(f"Falta {programa}: sudo apt install {programa}")
        raise typer.Exit(2)
    if not _es_url(origen) and not inicio and not fin and origen.lower().endswith(".mp3"):
        shutil.copy2(origen, destino)
    else:
        with t.spinner_ctx("Preparando la música"):
            ej.run(comando_importar(origen, destino, inicio, fin), timeout=None)
    t.ok(f"Música de {m.nombre} guardada en {destino}")


@musica.command("silenciar")
def cmd_silenciar() -> None:
    """Para la música y oculta la bocina hasta la próxima vez que entres en el modo."""
    sonido.silenciar()
    tema.actual().ok("Música silenciada.")


@musica.command("reproducir")
def cmd_reproducir() -> None:
    """Vuelve a poner la música del modo activo."""
    t = tema.actual()
    m = _modo(None)
    cfg = m.capas.get("musica") or {}
    archivo = m.recurso(cfg.get("archivo", "tema/musica.mp3"))
    if not sonido.reproducir(Ejecutor(), archivo, cfg):
        t.error("No hay música para este modo o falta mpv.")
        raise typer.Exit(1)
    t.ok("Sonando.")


@musica.command("estado")
def cmd_estado() -> None:
    """Muestra si suena música y si está silenciada."""
    t = tema.actual()
    datos = estado.leer()
    sonando = bool(datos.get("musica_pid"))
    t.info(f"Sonando: {'sí' if sonando else 'no'} · silenciada: "
           f"{'sí' if datos.get('musica_silenciada') else 'no'}")


@tema_app.command("importar")
def cmd_tema_importar(
    carpeta: Path = typer.Argument(..., exists=True, file_okay=False, help="Carpeta con recursos."),
    modo: str = typer.Option(None, "--modo", "-m", help="Modo (por defecto, el activo)."),
) -> None:
    """Copia fondo, iconos, sonidos, música y emblema al tema del modo."""
    t = tema.actual()
    m = _modo(modo)
    destino = m.dir_usuario() / "tema"
    copiados = importar_tema(carpeta, destino)
    for nombre in copiados:
        t.ok(nombre)
    if not copiados:
        t.aviso("No había nada que importar (fondo.*, iconos/, sonidos/, musica.mp3, emblema.png).")
    else:
        t.info(f"Vuelve a entrar en el modo para verlo: ultron entrar {m.id}")


def importar_tema(origen: Path, destino: Path) -> list[str]:
    destino.mkdir(parents=True, exist_ok=True)
    copiados = []
    for f in origen.iterdir():
        nombre = f.name.lower()
        valido = (f.is_dir() and nombre in ("iconos", "sonidos", "fuentes", "arranque")) or (
            f.is_file() and (nombre.startswith(("fondo", "emblema", "musica"))
                             or nombre in ("conky.conf",)))
        if not valido:
            continue
        if f.is_dir():
            shutil.copytree(f, destino / f.name, dirs_exist_ok=True)
        else:
            shutil.copy2(f, destino / f.name)
        copiados.append(f.name)
    return copiados
