# AGENTS.md: contrato común de Ultron

Lee este archivo, `PLAN.md` y `specs/diseno-terminal.md` antes de tocar nada. Cada bloque de
trabajo tiene su especificación en `specs/NN-*.md`. Implementa **solo** tu bloque, pero
respeta este contrato para que todas las piezas encajen.

## Producto
Ultron es un CLI en Python para **Ubuntu 24.04+ con GNOME** que transforma el sistema según
el modo: `netanyahu`, `focus`, `gaming`, `presentacion`, `fantasma`. Lo corrige un profesor
en su propio Ubuntu, con una IA local con API compatible con OpenAI. Se valora la
creatividad y las funcionalidades.

## Entorno de desarrollo (importante)
- Se desarrolla en **Windows** y se ejecuta en **Ubuntu**. El código tiene que **importar y
  pasar los tests en los dos**. Nada específico de Linux puede ejecutarse al importar.
- Las dependencias ya están instaladas en `.venv` y **no hay red**: no ejecutes `pip install`.
  Si necesitas un paquete nuevo, añádelo a `pyproject.toml` y prevé que falte
  (`try: import x except ImportError`).
- Tests: `.venv/Scripts/python -m pytest -q` (Windows) o `python -m pytest -q` (Linux).
  Lint: `.venv/Scripts/python -m ruff check ultron tests`.
- **No hagas `git commit`.** Lo hace el script de construcción.

## Pila
Python ≥ 3.10. Dependencias: `typer`, `rich`, `textual`, `pyyaml`, `httpx`, `pypdf`,
`genanki`, `pillow`, `tomli-w`, `dnspython` y `psutil`; usa `tomllib`, con `tomli` como
respaldo. Las herramientas del sistema (`gsettings`, `dconf`, `nmap`, `mpv`, `yt-dlp`,
`plymouth`…) se llaman **siempre** a través del `Ejecutor`.

## Idioma
- Todo lo que ve el usuario va en **español** (mensajes, ayuda de los comandos, errores, docs).
- Los identificadores van en español cuando suene natural (`aplicar`, `restaurar`, `modo_activo`).
  No mezcles idiomas dentro de un mismo nombre.

## Estructura del paquete
```
pyproject.toml            # nombre "ultron", script de consola: ultron = "ultron.cli:app"
ultron/
  __init__.py             # __version__
  __main__.py             # python -m ultron
  cli.py                  # app Typer raíz; registra los subcomandos de cada módulo
  nucleo/
    rutas.py              # rutas XDG: config, estado, datos, cache (respeta XDG_*; en Windows, ~/.ultron-dev)
    config.py             # Config (lee y escribe ~/.config/ultron/config.toml; permisos 600)
    ejecutor.py           # Ejecutor: único punto de entrada para comandos del sistema
    entorno.py            # detectar distro, versión de GNOME, Wayland/X11, comandos disponibles
    estado.py             # estado.json: modo activo, capas aplicadas, silencio de la música, XP
    motor.py              # entrar/salir/estado: orquesta capas, instantánea y rollback
    registro.py           # descubre los modos en ultron/modos/* y ~/.local/share/ultron/modos/*
    esquema.py            # carga y valida modo.yaml (dataclasses), con errores claros
  capas/
    base.py               # clase Capa (ver abajo) + REGISTRO_CAPAS
    shell.py terminal.py escritorio.py iconos.py cursor.py fuentes.py extensiones.py
    sonido.py musica.py widgets.py sistema.py arranque.py
  ia/
    cliente.py            # obtener_cliente(), interfaz ClienteIA
    openai_compat.py anthropic.py
    errores.py            # jerarquía IAError con mensaje y sugerencia en español
    util.py               # trocear texto, reparar JSON, contar tokens aproximados
    personalidad.py       # construye el prompt de sistema a partir del modo activo
  ui/
    tema.py               # Tema (tema.toml), consola Rich por modo, glifos, fallbacks
    banner.py animaciones.py selector.py (Textual) carga.py (pantalla de carga)
  compartidas/            # funciones de todos los modos (un módulo Typer por función)
  modos/
    <id>/
      __init__.py
      modo.yaml           # definición declarativa
      tema.toml           # interfaz de terminal del modo
      tema/               # recursos: fondo.png, musica.mp3, iconos/, sonidos/…
      funciones/__init__.py   # expone `app: typer.Typer` con los comandos propios del modo
extension/ultron@ultron/  # extensión GNOME Shell (ESM, GNOME 45+)
scripts/                  # instalar.sh, generar_iconos.py…
tests/
docs/
```

## Interfaces obligatorias

### Ejecutor (`ultron/nucleo/ejecutor.py`)
```python
@dataclass
class Resultado: codigo: int; salida: str; error: str

class Ejecutor:
    def __init__(self, simular: bool = False, consola=None): ...
    simular: bool
    historial: list[list[str]]       # todos los comandos pedidos, también al simular
    def run(self, cmd: list[str], *, sudo=False, check=True, entrada: str | None = None,
            timeout: float | None = 60, fondo=False) -> Resultado
    def existe(self, programa: str) -> bool          # shutil.which
    def gsettings_get(self, esquema: str, clave: str) -> str | None
    def gsettings_set(self, esquema: str, clave: str, valor: str) -> None
    def escribir(self, ruta: Path, contenido: str | bytes, *, sudo=False, modo: int | None = None)
    def borrar(self, ruta: Path, *, sudo=False)
    def copiar(self, origen: Path, destino: Path, *, sudo=False)
```
- Al simular, `run`/`escribir`/`borrar`/`copiar` **no hacen nada**: lo registran y lo
  pintan; las lecturas (`gsettings_get`, `existe`) sí se ejecutan.
- `sudo=True` antepone `sudo` (o `pkexec` si no hay terminal). Los errores lanzan
  `ErrorEjecucion` con un mensaje en español.
- Los tests usan `EjecutorFalso` (en `tests/conftest.py`), que graba los comandos y devuelve
  respuestas programadas. **Ningún test ejecuta comandos reales del sistema.**

### Capa (`ultron/capas/base.py`)
```python
class Capa(ABC):
    nombre: ClassVar[str]               # "escritorio"
    requiere_sudo: ClassVar[bool] = False
    orden: ClassVar[int] = 50           # orden de aplicación; se restaura en orden inverso
    def __init__(self, ej: Ejecutor, ctx: "Contexto"): ...
    def disponible(self) -> tuple[bool, str]          # ¿se puede aplicar en este sistema? y por qué no
    def capturar(self, cfg: dict) -> dict             # estado actual de lo que vas a tocar (JSON)
    def aplicar(self, cfg: dict) -> None
    def restaurar(self, previo: dict) -> None         # deja exactamente lo capturado
REGISTRO_CAPAS: dict[str, type[Capa]]                 # se rellena con @registrar_capa
```
`Contexto` tiene `modo` (ModoDef), `dir_modo` (Path), `rutas` y `consola`. Una capa **nunca**
borra lo que no ha creado ella. Lo que instala va en `~/.local/share/ultron/…` o en rutas que
apunta en su estado.

### Motor (`ultron/nucleo/motor.py`)
- `entrar(id, simular=False, solo=None, excepto=None, progreso=callback)`:
  1. si hay otro modo activo, primero `salir()`;
  2. para cada capa del modo, ordenadas por `orden`: `disponible()` → si no, se salta y avisa;
     `capturar()` → se guarda **inmediatamente** en `~/.local/state/ultron/instantanea.json`;
     `aplicar()`;
  3. si una capa falla, se restaura todo lo aplicado hasta ese momento y se informa.
- `salir()` restaura en orden inverso a partir de la instantánea, aunque el proceso anterior
  se cortara a medias. Después borra la instantánea.
- Las capas con `requiere_sudo` se agrupan: se avisa **una vez**, se pide confirmación y se
  pueden saltar con `--sin-sudo`.
- `progreso(capa, estado)` alimenta la pantalla de carga (`ui/carga.py`).

### Definición de modo (`modo.yaml`)
```yaml
id: netanyahu
nombre: NETANYAHU
lema: "Acceso concedido"
descripcion: "Hacker israelí con OSINT y hacking ético"
ia:
  personalidad: |
    Eres ULTRON en modo NETANYAHU, analista de inteligencia...
  temperatura: 0.6
capas:              # cada clave es una capa; su valor es el cfg que recibe
  shell: {...}
  escritorio: {...}
funciones: [osint, radar, auditar]   # nombres de comandos que aporta (para ayuda y selector)
recursos_opcionales:                 # lo que doctor revisa; si falta, se avisa sin fallar
  - {ruta: tema/fondo.png, descripcion: "Fondo de Netanyahu (GPT Images)"}
```
Las rutas relativas del YAML se resuelven respecto a la carpeta del modo.

### Tema de terminal (`tema.toml`)
Ver `specs/diseno-terminal.md`. Las claves son `paleta`, `bordes`, `glifos`, `glifos_ascii`,
`prompt`, `banner` (texto multilínea), `banner_compacto`, `spinner` (lista de fotogramas),
`entrada` (`escritura`|`glitch`|`fundido`) y `voz` (frases de ok, error y aviso).
`ui.tema.consola()` devuelve una consola Rich con el tema del **modo activo**; sin modo
activo, el tema `ultron` por defecto (cian/gris). **Toda** la salida de Ultron pasa por
`ui.tema`.

### IA (`ultron/ia/`)
```python
class ClienteIA(Protocol):
    proveedor: str; modelo: str
    def chat(self, mensajes: list[dict], *, temperatura: float | None = None,
             max_tokens: int | None = None, json: bool = False) -> str
    def chat_stream(self, mensajes: list[dict], **kw) -> Iterator[str]
    def modelos(self) -> list[str]
    def probar(self) -> "Diagnostico"     # llamada real mínima; nunca lanza, devuelve ok/error
def obtener_cliente(modelo: str | None = None) -> ClienteIA   # lanza IANoConfigurada
def preguntar(prompt: str, *, sistema: str | None = None, json=False, **kw) -> str  # usa la personalidad del modo activo
```
- Prioridad de la configuración: argumentos > variables de entorno `ULTRON_PROVEEDOR`,
  `ULTRON_URL_BASE`, `ULTRON_MODELO`, `ULTRON_API_KEY` > `config.toml` > autodetección
  (Ollama en `localhost:11434`, LM Studio en `localhost:1234`).
- Solo se usa `httpx` (nada de SDK de OpenAI ni Anthropic). Timeout de 120 s.
- Los errores se traducen a `IAError` con `mensaje` y `sugerencia` en español: `SinConexion`,
  `URLIncorrecta`, `ClaveInvalida`, `ModeloNoExiste`, `SinSaldo`, `ContextoExcedido`,
  `TiempoAgotado` y `RespuestaInvalida`. **Ninguna traza de Python llega al usuario.**
- Pensado para **modelos locales pequeños**: prompts breves, `util.trocear()` por tamaño,
  `util.reparar_json()` tolerante (bloques ```json, comas finales, texto alrededor) y un
  reintento pidiendo "solo JSON".
- Las funciones que usan IA, si no hay IA configurada, dicen "Configura la IA con
  `ultron ia configurar`" y salen con código 2. Las que no usan IA nunca dependen de ella.

### CLI
- `ultron/cli.py` registra: núcleo (`entrar`, `salir`, `estado`, `modos`, `doctor`,
  `instalar`, `desinstalar`), el grupo `ia`, cada módulo de `compartidas/` y el `app` de cada
  modo (sus comandos están **siempre** disponibles; el modo activo solo cambia el aspecto y
  la personalidad de la IA).
- `ultron` sin argumentos abre el selector (`ui/selector.py`); si no hay TTY, muestra la ayuda.
- Opciones globales: `--simular`, `--sin-animaciones`, `--sin-color`. Respeta `NO_COLOR`,
  `ULTRON_SIN_ANIMACIONES` y las salidas que no son TTY.
- Código de salida 0 si va bien, 1 si hay error, 2 si falta configuración o dependencias.

### Dependencias del sistema
Cada función que necesite un programa externo lo comprueba con `ej.existe()` y, si falta,
dice qué paquete de apt instalar. `ultron instalar` instala la lista completa de
`ultron/nucleo/dependencias.py` (paquetes apt por modo + extensiones GNOME por UUID).

## Reglas de calidad
- Cada bloque añade sus tests en `tests/test_<bloque>_*.py`. Cubre la lógica, la generación
  de comandos (comprobando el `historial` del `EjecutorFalso`), los errores y el modo
  simulado.
- Nada de `print`: usa la consola del tema.
- Funciones cortas, docstrings breves en español y anotaciones de tipo.
- Seguridad: nunca `shell=True` con datos del usuario; los comandos que propone la IA se
  enseñan y **solo se ejecutan si se confirman**; sin datos personales en la telemetría
  (no hay telemetría).
- Hacking/OSINT: solo información pública, o la red y el equipo propios. Cada comando de
  escaneo muestra un aviso de uso ético la primera vez.
- La música (`ultron/modos/*/tema/musica.mp3`) está en `.gitignore`. Se añade con
  `ultron musica importar <url-o-archivo>`, y `doctor` explica cómo hacerlo.
