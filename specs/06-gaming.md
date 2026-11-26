# Bloque 06: modo GAMING (cyberpunk)

## Objetivo
Que **no parezca Ubuntu**: hiperfuturista, neón, cyberpunk y animado. Lo principal es la
estética; las funciones son pocas pero útiles y con aspecto de HUD de videojuego. La
interfaz de la terminal es la de `specs/diseno-terminal.md` (degradado
magenta → violeta → cian, glitch, XP).

## `modo.yaml` (estética máxima)
- **Paleta:** magenta `#FF00E6`, violeta `#8A2BE2`, cian `#00F0FF`, amarillo `#FFE600`,
  lima `#39FF14` y fondo `#0B0B16`.
- **terminal:** fondo `#0B0B16` con un 12 % de transparencia, la paleta neón, el cursor
  magenta y la fuente JetBrains Mono Nerd.
- **escritorio:**
  - fondo **generado** (`generar_recursos.py`): una ciudad cyberpunk procedural en Pillow,
    con siluetas de rascacielos en capas con ventanas de colores, un sol retrowave a
    franjas, una rejilla en perspectiva con brillo neón, scanlines y el texto "ULTRON" con
    efecto glow. Es de 3840×2160 y se puede regenerar con otra semilla con `ultron gaming
    fondo --semilla N`;
  - fondo de bloqueo con la misma ciudad desenfocada;
  - tema GTK y del shell neón: panel superior negro translúcido con un borde inferior
    degradado, menús con brillo en el borde y botones con hover en cian;
  - fuente de la interfaz **Rajdhani** u **Orbitron** (títulos) y animaciones activadas.
- **iconos:** tinte neón, con `tinte` por categorías: carpetas en magenta, apps en cian
  y archivos en violeta. Efecto glow opcional en los PNG (un desenfoque del contorno en
  color sobre transparente).
- **cursor:** Bibata Modern (Ice o una variante recoloreada en cian), tamaño 32.
- **extensiones** (todas instaladas por `ultron instalar --modo gaming`; los UUID se
  comprueban contra extensions.gnome.org al instalar):
  - `burn-my-windows@schneegans.github.com`: efectos al abrir y cerrar ventanas (Glitch,
    TV, Energize A, Pixelate). Perfil propio con colores neón;
  - `compiz-windows-effect@hermes83.github.com`: ventanas gelatinosas;
  - `desktop-cube@schneegans.github.com`: cubo 3D entre escritorios;
  - `blur-my-shell@aunetx`: desenfoque del panel, la vista general y el dock;
  - `user-theme@gnome-shell-extensions.gcampax.github.com`;
  - `openbar@neuromorph`: panel superior estilo isla o flotante con bordes neón (si está
    disponible para la versión de GNOME);
  - `rounded-window-corners@fxgn`: esquinas redondeadas;
  - `hanabi-extension@jeffshee.github.io`: **fondo de vídeo animado** con
    `tema/fondo.mp4` si existe; si no, se desactiva y se usa el fondo estático;
  - `just-perfection-desktop@just-perfection`: oculta los elementos de Ubuntu (el logo de
    Actividades, etc.) para que no parezca Ubuntu;
  - `space-bar@luchrioh`: escritorios numerados estilo tiling.
- **widgets:** Conky HUD con un anillo de CPU, RAM y GPU con `lua` (si `conky-all` trae
  cairo; si no, barras), temperaturas, red, reloj grande Orbitron y "PLAYER: <usuario> LVL
  N".
- **sonido:** sonidos futuristas generados de forma sintética (barridos de frecuencia):
  entrada, notificación, error y salida.
- **sistema:** `perfil_energia: performance`.
- **arranque:** Plymouth "cyberpunk" con el logo ULTRON con glitch (fotogramas generados) y
  barra de carga neón; GRUB y GDM con la ciudad.
- **dependencias:** `cava`, `mangohud`, `gamemode`, `conky-all`, `chafa`, `ffmpeg`,
  `wf-recorder` (Wayland), `gpu-screen-recorder` si está disponible (si no, se usa ffmpeg con
  x11grab o el grabador integrado de GNOME por dbus) y `lm-sensors`. Fuentes Orbitron,
  Rajdhani y JetBrains Mono Nerd.
- **recursos_opcionales:** `tema/fondo.mp4` (un vídeo libre de Pexels o Pixabay de una
  ciudad cyberpunk en bucle).

## Funciones
- **`ultron juegos`:**
  - biblioteca unificada que lee Steam (`~/.steam/steam/steamapps/*.acf` + `libraryfolders.vdf`
    con un parser VDF propio), Lutris (`~/.local/share/lutris/pga.db`), Flatpak (`flatpak
    list --app` filtrado por las categorías Game) y los `.desktop` con `Categories=Game`;
  - una cuadrícula de "cartas" con Rich y, si existe `chafa`, la **portada** en la terminal
    (las de Steam desde `https://cdn.cloudflare.steamstatic.com/steam/apps/<appid>/header.jpg`,
    en caché);
  - lanzar por número o nombre (búsqueda difusa) con `gamemoderun` y MangoHud si están
    activos;
  - `--demo` con juegos de ejemplo.
- **`ultron turbo [on|off|estado]`:** GameMode, `powerprofilesctl performance`, desactivar el
  indexado (`tracker3 daemon --pause-for` si existe, o `systemctl --user stop
  tracker-miner-fs-3`), notificaciones desactivadas y vaciar la caché de páginas (con
  sudo, opcional). Muestra un antes y un después de la RAM libre y los procesos que más
  gastan, con un botón de "matar" (con confirmación). `off` lo restaura todo.
- **`ultron hud`:** pantalla completa con Rich Live o Textual:
  - CPU por núcleo, GPU (`nvidia-smi`, o `/sys/class/drm/card*/device/gpu_busy_percent` en
    AMD, o "N/D"), RAM, swap, temperaturas (`psutil.sensors_temperatures`), red
    subida y bajada con un sparkline, disco y los procesos que más consumen;
  - todo con estética de HUD: barras de HP, MP y XP, bordes `HEAVY` y el degradado;
  - `q` para salir.
- **`ultron fps [on|off]`:** activa MangoHud para los juegos lanzados desde Ultron y escribe
  `~/.config/MangoHud/MangoHud.conf` con un estilo neón propio (colores, posición
  arriba a la izquierda y la fuente).
- **`ultron clip [--segundos 30]`:** grabación de los últimos N segundos con un búfer
  circular (`gpu-screen-recorder -r` si existe; si no, `wf-recorder` o `ffmpeg` por
  segmentos de 5 s, y al pedir el clip se concatenan con ffmpeg). `ultron clip guardar`
  (se puede asignar a un atajo de teclado con `gsettings` en la capa `sistema`:
  Super+Alt+R). Los clips van a `~/Vídeos/Ultron/`.
- **`ultron visualizador`:** lanza `cava` con una configuración neón generada (degradado de
  colores), en una terminal nueva si se pide `--ventana`.
- **XP y logros (`ultron/nucleo/xp.py`, compartido, pero solo se muestra en gaming):**
  - cada comando suma XP (la tabla está en el módulo) y el nivel = floor(sqrt(xp/50));
  - 15 logros (por ejemplo "Noctámbulo": usar Ultron entre las 2 y las 5; "Políglota":
    entrar en los 5 modos; "Analista": 10 OSINT; "Empollón": 10 pomodoros; "Speedrun":
    entrar y salir de un modo en menos de 30 s…);
  - al subir de nivel o desbloquear un logro, banner animado y sonido;
  - `ultron perfil` muestra la ficha del jugador.

## IA del modo
"Eres ULTRON en modo GAMING: un compañero gamer cyberpunk, con energía y en jerga gamer
pero útil. Das trucos, guías, builds y ajustes de rendimiento para Linux (Proton, Wine,
drivers). Respuestas cortas y con emojis de texto como ⚡ ▶ ★."

## Criterios de aceptación
- Tests:
  - el parser VDF y ACF con archivos de ejemplo;
  - la detección de juegos de los `.desktop`;
  - la búsqueda difusa;
  - el generador del fondo (imagen de 3840×2160, determinista con la semilla, en menos de
    10 s; en el test a 640×360);
  - la tabla de XP y niveles, y 5 logros;
  - turbo on/off con su restauración en el historial;
  - la configuración de MangoHud y cava;
  - el búfer circular de clips (la lógica de segmentos y de concatenación).
- `ultron hud --demo --una-vez` pinta un fotograma (para el test y el README).
