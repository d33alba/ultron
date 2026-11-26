# Bloque 01: núcleo, motor de modos y motor de temas

## Objetivo
Dejar el esqueleto completo y funcionando: el paquete instalable, el motor de modos con
instantánea y rollback, el motor de temas de terminal y los comandos base. Las capas reales
llegan en el bloque 03; aquí solo hay `Capa`, su registro y una capa `shell` completa como
referencia.

## Archivos
- Todo lo de `ultron/nucleo/`, `ultron/capas/base.py`, `ultron/capas/shell.py`,
  `ultron/ui/tema.py`, `ultron/ui/banner.py`, `ultron/ui/animaciones.py`, `ultron/cli.py`,
  `ultron/__init__.py` y `ultron/__main__.py`.
- `pyproject.toml` (hatchling o setuptools; incluye los datos de `ultron/modos/**`;
  extras `dev`; configuración de ruff con line-length 100).
- Esqueleto de los 5 modos más un tema por defecto:
  - `ultron/modos/{netanyahu,focus,gaming,presentacion,fantasma}/`, cada uno con
    `__init__.py`, `modo.yaml` (de momento solo con id, nombre, lema, descripción, ia y la
    capa `shell`), `tema.toml` **completo** y `funciones/__init__.py` con un `app` Typer vacío.
  - Tema por defecto en `ultron/ui/tema_defecto.toml`.
- `tests/conftest.py` con `EjecutorFalso`, un `tmp_home` (que redirige XDG_* y HOME a
  tmp_path) y fixtures de modo.

## Temas de terminal (`tema.toml`)
Los de netanyahu, focus y gaming tienen que coincidir con `specs/diseno-terminal.md`:
banners, paletas, glifos, prompts, spinners y voz. Diseña dos más con la misma calidad:
- **presentacion:** escenario y teatro. Blanco sobre gris carbón, un acento dorado
  `#F2C14E`, bordes `ROUNDED`, glifos `▶ ■ ● ◆`, banner con un "telón" de caracteres
  `▓▒░` a los lados, y voz de presentador ("Damas y caballeros…", "Siguiente.").
- **fantasma:** blanco hueso `#E8E8E8` y gris niebla `#5A5A5A` sobre negro, bordes `MINIMAL`
  o ninguno, glifos `◌ ⋯ ✝ ·`, un banner con un fantasma ASCII que se desvanece (usa `░` y
  caracteres medio transparentes), voz en susurro, en minúsculas y con puntos suspensivos.
  El prompt muestra `◌ anónimo`.

## Motor de temas (`ui/tema.py`)
- `cargar_tema(id_modo|None) -> Tema` y `consola() -> Console` (en caché; se invalida al
  cambiar de modo).
- `Tema.estilo(nombre)` para `primario|secundario|acento|ok|aviso|error|apagado`,
  `Tema.glifo(nombre)` (con respaldo ASCII si la terminal no soporta Unicode),
  `Tema.panel(contenido, titulo)`, `Tema.tabla(...)`, `Tema.ok/aviso/error/info(msg)` y
  `Tema.spinner(texto)` (un context manager).
- Detecta el soporte de color (truecolor, 256 o 16), de Unicode (por la codificación de
  stdout y `LANG`) y el ancho de la terminal (banner compacto con menos de 80 columnas).
- `ui/banner.py`: `mostrar_banner(tema, animado=True)`. Soporta degradados horizontales
  (gaming) y medición con `wcwidth` para el hebreo (netanyahu), con la línea de respaldo
  "SHALOM" si descuadra.
- `ui/animaciones.py`: `escritura`, `glitch`, `fundido` y `transicion(tema_viejo,
  tema_nuevo, pasos)`. Todas duran menos de 1,5 s y no hacen nada si las animaciones están
  desactivadas.

## Capa `shell` (de referencia)
- Escribe `~/.config/ultron/shell/ultron.sh` con el prompt del modo (`PS1` con colores ANSI
  sacados del tema), los alias, las variables y un mensaje de bienvenida (`ultron
  bienvenida`, que muestra el banner compacto).
- Garantiza **una sola vez** este bloque en `~/.bashrc`:
  `# >>> ultron >>>\n[ -f ~/.config/ultron/shell/ultron.sh ] && . ~/.config/ultron/shell/ultron.sh\n# <<< ultron <<<`
- `capturar` guarda si existía el bloque y el contenido anterior de `ultron.sh`. `restaurar`
  deja `ultron.sh` vacío (prompt original) y quita el bloque solo si lo añadió Ultron.
- cfg: `prompt` (plantilla con `{usuario}`, `{host}`, `{dir}`, `{modo}` y `{extra}`, donde
  `{extra}` es la salida de `ultron prompt-extra`, que se usa para el pomodoro y la XP),
  `alias` (dict), `variables` (dict), `historial` (bool; si es false,
  `HISTFILE=/dev/null`) y `bienvenida` (bool).
- Comando oculto `ultron prompt-extra`: rápido (< 50 ms; **no** importa rich ni la IA; lee
  `estado.json`).

## Comandos del bloque
- `ultron modos`: tabla con todos los modos; cada fila se pinta con la paleta de su modo y
  muestra glifo, nombre, lema y funciones. `--detalle <id>` muestra el banner y las capas.
- `ultron entrar <id> [--simular] [--solo capa,capa] [--excepto capa] [--sin-sudo] [--si]`:
  transición animada y progreso por capa (`▸ capa  ✔/⠹/✖/saltada`). Al terminar, el banner
  del modo y "abre una terminal nueva para ver el prompt".
- `ultron salir [--simular]` y `ultron estado` (modo, desde cuándo, capas aplicadas y
  saltadas, y si hay una instantánea pendiente).
- `ultron doctor`: esqueleto extensible. Cada módulo registra comprobaciones con
  `@comprobacion("nombre")` en `nucleo/doctor.py`, y se pinta una tabla con ✔/⚠/✖ y la
  solución de cada fila. En este bloque comprueba la distro y la versión de GNOME, Wayland,
  los comandos básicos y los recursos opcionales de cada modo.
- `ultron bienvenida` (oculto).
- `ultron --version`.

## Criterios de aceptación
- `.venv/Scripts/python -m ultron modos` funciona en Windows y enseña los 5 modos con su
  estilo.
- `ultron entrar netanyahu --simular` lista los comandos o escrituras que haría y no toca
  nada.
- Tests:
  - motor: el orden de las capas, la instantánea escrita **antes** de aplicar, el rollback
    cuando falla la capa N, que `salir` restaure en orden inverso, la recuperación tras
    un corte a medias, y que entrar en B con A activo haga salir de A primero;
  - capa shell: que sea idempotente y que restaure;
  - esquema: errores claros con YAML inválido;
  - tema: los fallbacks sin Unicode y sin color.
- `ruff check` limpio.
