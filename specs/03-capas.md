# Bloque 03: capas que transforman Ubuntu, extensión GNOME, instalador

## Objetivo
Implementar todas las capas para que, en Ubuntu 24.04 con GNOME, cada modo cambie **todo**
lo estético: fondo, tema GTK y del shell, iconos (apps, carpetas, archivos), cursor, fuentes,
sonidos, música, extensiones (animaciones), widgets, terminal y arranque. Todo reversible con
`ultron salir`. Además: la extensión `ultron@ultron`, la pantalla de carga, `ultron
instalar/desinstalar`, la música y la importación de temas.

Cada capa: `capturar` lee el valor actual de **cada** clave que va a tocar; `restaurar` vuelve
a escribirlo exactamente (si una clave estaba en su valor por defecto, hace `gsettings reset`).
Todas usan el `Ejecutor` y tienen tests con `EjecutorFalso` que comprueban los comandos
exactos.

## Capas (cfg en `modo.yaml`)

### `terminal` (orden 20)
- Crea un perfil de GNOME Terminal "Ultron-<modo>" por `dconf`
  (`/org/gnome/terminal/legacy/profiles:/:<uuid>/`) con la paleta de 16 colores, el fondo,
  el texto, la fuente, la transparencia, el cursor y `use-theme-colors=false`.
- Lo pone como perfil por defecto. `capturar` guarda `default` y `list`; `restaurar`
  vuelve a dejarlos y borra el perfil creado.
- cfg: `paleta: [16 hex]`, `fondo`, `texto`, `fuente: "JetBrains Mono 12"`,
  `transparencia: 0-100` y `cursor: block|ibeam|underline`.
- Si existe `ptyxis` (Ubuntu 25.04+), aplica el equivalente por `gsettings` de
  `org.gnome.Ptyxis` (con una paleta propia en `~/.local/share/org.gnome.Ptyxis/palettes/`).

### `escritorio` (orden 30)
- **Fondo:** `org.gnome.desktop.background` `picture-uri` y `picture-uri-dark`,
  `picture-options`, `primary-color`. Además la **pantalla de bloqueo**:
  `org.gnome.desktop.screensaver picture-uri`.
- **Estilo:** `org.gnome.desktop.interface` `color-scheme`, `gtk-theme`, `accent-color`
  (GNOME 47+), `font-name`, `monospace-font-name`, `enable-animations` y `clock-show-seconds`.
- **Tema GTK propio por modo**, generado a partir de la paleta:
  - escribe `~/.local/share/themes/Ultron-<modo>/gtk-3.0/gtk.css` y `gtk-4.0/gtk.css` con
    `@define-color` (accent, window_bg, headerbar_bg, view_bg, card_bg, sidebar_bg…, de
    libadwaita) y algunas reglas propias (barras de título, botones, selección);
  - también `~/.config/gtk-4.0/gtk.css`, de forma reversible: guarda el original y
    restaura; libadwaita lo lee para las apps GTK4.
- **Tema del shell:** con la extensión `user-theme` activa, genera
  `~/.local/share/themes/Ultron-<modo>/gnome-shell/gnome-shell.css` a partir de una
  plantilla con la paleta (panel superior, dash, menús, OSD, notificaciones) y fija
  `org.gnome.shell.extensions.user-theme name`.
- **Dock** (Ubuntu Dock / dash-to-dock): `dock-position`, `dash-max-icon-size`,
  `extend-height`, `transparency-mode`, `background-opacity`, `custom-background-color`,
  `background-color` y `autohide`.
- cfg: `fondo`, `fondo_bloqueo`, `esquema: oscuro|claro`, `acento`, `tema_gtk: generar|<nombre>`,
  `tema_shell: generar|<nombre>|null`, `fuente_ui`, `fuente_mono`, `animaciones: bool` y
  `dock: {...}`.

### `iconos` (orden 35)
- Ejecuta `scripts/generar_iconos.py` (importable como `ultron.capas.iconos_gen`) para crear
  `~/.local/share/icons/Ultron-<modo>/`:
  1. busca el tema base (`/usr/share/icons/Yaru`, y si no `Adwaita`);
  2. para cada PNG o SVG de `apps`, `places`, `mimetypes`, `devices`, `status` y `actions`,
     en todos los tamaños, lo recolorea con la transformación del cfg:
     - `tinte`: mapeo de tonos (los naranjas y morados de Yaru → el color primario del modo)
       con HSV en Pillow para PNG;
     - para SVG, sustitución de los colores hex o rgb del archivo por el más cercano de la
       paleta del modo;
  3. opcionalmente superpone un emblema (`tema/emblema.png`; por ejemplo, la estrella de
     David) en la esquina inferior derecha de las carpetas (`places/folder*`);
  4. copia **encima** los iconos personalizados de `tema/iconos/<nombre-icono>.png|svg`
     (por ejemplo `firefox.png`, `org.gnome.Calculator.png`, `org.gnome.Nautilus.png`), en
     todos los tamaños con redimensionado;
  5. escribe `index.theme` (`Inherits=Yaru,Adwaita,hicolor`) y ejecuta
     `gtk-update-icon-cache`.
- Usa caché: si el hash de (cfg + archivos de `tema/iconos` + versión del script) no ha
  cambiado, no regenera. Es multiproceso y muestra el progreso en la pantalla de carga.
  Objetivo: menos de 60 s la primera vez y menos de 1 s con caché.
- Fija `org.gnome.desktop.interface icon-theme`; `restaurar` lo devuelve a su valor (la
  carpeta generada se queda como caché; `ultron desinstalar` la borra).
- **Iconos de las apps de Flatpak/Snap** que no respetan el tema: crea overrides `.desktop`
  en `~/.local/share/applications/` con `Icon=` apuntando al icono generado, apuntados para
  borrarlos al restaurar.
- cfg: `base`, `tinte: {objetivo: "#0038B8", intensidad: 0-1, saturacion: x}`, `emblema`,
  `emblema_en: [places]`, `personalizados: tema/iconos` y `monocromo: bool` (para focus y
  fantasma).

### `cursor` (orden 36) y `fuentes` (orden 10)
- `cursor`: `cursor-theme` y `cursor-size`. Si cfg `generar: true`, crea un tema de cursor
  recoloreando los PNG de `Yaru` con `xcursorgen` (si existe; si no, usa uno instalado de
  `dependencias.py`, como Bibata).
- `fuentes`: copia los `.ttf`/`.otf` de `tema/fuentes/` (o los instalados con `ultron
  instalar`) a `~/.local/share/fonts/ultron/` y ejecuta `fc-cache -f`.

### `extensiones` (orden 40)
- Activa o desactiva extensiones de GNOME **ya instaladas** (`gnome-extensions
  enable/disable`) y fija su configuración con `gsettings --schemadir` o `dconf write` bajo
  `/org/gnome/shell/extensions/<x>/`.
- `capturar` guarda `org.gnome.shell enabled-extensions` y `disabled-extensions` y los
  valores de dconf que toca.
- Si una extensión no está instalada: aviso, "ejecuta `ultron instalar`" y se salta.
- cfg: `activar: [uuid]`, `desactivar: [uuid]` y `ajustes: {uuid: {clave: valor-gvariant}}`.

### `sonido` (orden 45) y `musica` (orden 90)
- `sonido`: tema de sonido propio en `~/.local/share/sounds/Ultron-<modo>/` (`index.theme`
  y los `.oga` de `tema/sonidos/`), `org.gnome.desktop.sound theme-name` y
  `event-sounds`. Opcionalmente reproduce `tema/sonidos/entrada.oga` al entrar
  (`paplay`/`pw-play`).
- `musica`: si existe `tema/musica.mp3` y **no** está silenciada, la reproduce con `mpv
  --no-video --really-quiet [--loop]` en segundo plano. Guarda el PID en `estado` y pone
  `musica_sonando=true` en `~/.local/state/ultron/panel.json`, que lee la extensión para
  enseñar la bocina.
- `ultron musica silenciar` (lo llama la extensión): mata `mpv`, guarda
  `musica_silenciada=true` y quita la bocina.
- **Al entrar en un modo** se borra `musica_silenciada`, así que la música vuelve a sonar.
  `restaurar` mata el reproductor.
- cfg: `archivo`, `bucle: bool`, `volumen: 0-100` y `fundido_entrada_s`.

### `widgets` (orden 60)
- Conky: escribe `~/.config/ultron/conky/<modo>.conf` a partir de `tema/conky.conf.j2` (o
  una plantilla del modo), con la paleta. Lo lanza con `conky -d -c ...` y guarda el PID.
- Autoarranque: `~/.config/autostart/ultron-widgets.desktop`, para que vuelva tras reiniciar
  mientras el modo esté activo. `restaurar` mata Conky y borra el `.desktop`.
- Si no hay conky, se salta.

### `sistema` (orden 70; sudo solo para hosts)
- Notificaciones (`org.gnome.desktop.notifications show-banners`), energía
  (`org.gnome.desktop.session idle-delay`, `org.gnome.settings-daemon.plugins.power`),
  `night-light` y la escala del texto.
- **Bloqueo de webs:** inserta un bloque `# >>> ultron` en `/etc/hosts` con sudo; se
  restaura quitando ese bloque.
- **Perfil de CPU:** `powerprofilesctl set performance|balanced|power-saver`.
- cfg: `notificaciones`, `suspension_min`, `luz_nocturna`, `escala_texto`, `bloquear: [dominios]`
  y `perfil_energia`.

### `arranque` (orden 95, requiere sudo; desactivada por defecto, se activa con `--arranque` o en config)
- **Plymouth:** instala el tema `ultron-<modo>` en `/usr/share/plymouth/themes/` (un script de
  Plymouth con `tema/arranque/logo.png`, fondo de color y animación de puntos o de
  progreso). Lo activa con `update-alternatives --set default.plymouth` (o
  `plymouth-set-default-theme`) y luego `update-initramfs -u`. Avisa de que tarda alrededor
  de 1 minuto.
- **GRUB:** imagen de fondo (`GRUB_BACKGROUND`) y colores (`GRUB_COLOR_NORMAL`) en
  `/etc/default/grub.d/99-ultron.cfg`, seguido de `update-grub`.
- **GDM:** fondo de la pantalla de inicio de sesión con `/etc/dconf/db/gdm.d/99-ultron`
  (`[org/gnome/desktop/background]` y `[org/gnome/desktop/interface]`), seguido de
  `dconf update`. Avisa de que el CSS completo de GDM no se toca.
- `restaurar` deja la alternativa anterior, borra los archivos de Ultron y vuelve a ejecutar
  `update-initramfs`/`update-grub`/`dconf update`.

## Extensión `extension/ultron@ultron/` (GNOME 45–48, ESM)
- `metadata.json` (`shell-version` 45, 46, 47 y 48), `extension.js` y `stylesheet.css`.
- Indicador en el panel superior derecho:
  - glifo y nombre del modo (lee `~/.local/state/ultron/panel.json` con `Gio.FileMonitor`);
  - **botón de bocina** (`audio-volume-high-symbolic`) visible solo si
    `musica_sonando && !musica_silenciada`; al pulsarlo ejecuta
    `ultron musica silenciar` (`GLib.spawn_command_line_async`) y se oculta;
  - texto del pomodoro (`◑ 18:42`) si `pomodoro` existe;
  - XP y nivel en modo gaming.
- Menú desplegable: cambiar de modo (lista de `panel.json.modos`; ejecuta `ultron entrar
  <id> --si --sin-animaciones`), `Salir del modo` y `Abrir Ultron` (una terminal con
  `ultron`).
- El color del indicador sale de `panel.json.acento`.
- `ultron instalar` copia la extensión a `~/.local/share/gnome-shell/extensions/` y la
  activa. Tests: `node --check` si hay Node (se salta si no), y un test en Python que
  valida `metadata.json`.

## `ultron/nucleo/panel.py`
Escribe `panel.json` de forma atómica (`modo`, `nombre`, `glifo`, `acento`, `musica_sonando`,
`musica_silenciada`, `pomodoro`, `xp`, `nivel` y `modos`). Lo usan el motor, la música, el
pomodoro y la XP.

## Pantalla de carga (`ui/carga.py`)
- Si hay sesión gráfica y PyGObject con Gtk 4 (`gi.require_version('Gtk','4.0')`), abre una
  ventana a pantalla completa:
  - fondo del modo (o su color primario), banner o logo del modo, nombre de la capa
    actual y barra de progreso;
  - una animación sencilla con `Gtk.DrawingArea`, propia de cada modo: estrella girando
    (netanyahu), respiración (focus), líneas de escaneo neón (gaming), telón (presentación)
    o niebla (fantasma).
  - Se alimenta con el callback `progreso` del motor, que se ejecuta en un hilo, con
    `GLib.idle_add`, y se cierra sola al terminar.
- Si no se puede, muestra el progreso con Rich en la terminal (siempre en Windows y en CI).
- Opción `--sin-carga`.

## `ultron instalar` / `ultron desinstalar`
- `nucleo/dependencias.py`: paquetes de apt comunes (`mpv`, `conky-all`, `gnome-shell-extensions`,
  `gnome-shell-extension-manager`, `gnome-tweaks`, `python3-gi`, `gir1.2-gtk-4.0`,
  `x11-apps`, `fonts-jetbrains-mono`, `plymouth-themes`, `yt-dlp`, `ffmpeg`, `chafa`,
  `jq`) y paquetes por modo (los define cada modo en `modo.yaml: dependencias: {apt:[], extensiones:[], fuentes:[]}`).
- **Extensiones de extensions.gnome.org:** para cada UUID, consulta
  `https://extensions.gnome.org/extension-info/?uuid=<uuid>&shell_version=<ver>`, descarga el
  zip y ejecuta `gnome-extensions install --force`.
- **Fuentes de Google Fonts o GitHub** (Orbitron, Rajdhani, Inter, JetBrains Mono Nerd):
  URLs fijas en `dependencias.py`, guardadas en `~/.local/share/fonts/ultron/`.
- Resumen claro al principio (qué se va a instalar, cuánto ocupa aproximadamente, que pide
  sudo para apt) con confirmación, y al final: "**Cierra sesión y vuelve a entrar una vez**
  para que GNOME cargue las extensiones (Wayland)".
- Opciones: `--modo X` (solo lo de ese modo), `--sin-apt` y `--simular`.
- `ultron desinstalar`: sale del modo activo, desactiva y borra las extensiones instaladas
  por Ultron (las apunta en `instaladas.json`), borra temas, iconos, sonidos y fuentes, el
  bloque de `.bashrc` y la configuración (preguntando antes).

## `ultron musica` y `ultron tema`
- `ultron musica importar <url|archivo> [--modo netanyahu] [--inicio 0:30 --fin 2:00]`:
  - con un archivo, lo convierte o recorta con `ffmpeg` a `tema/musica.mp3`;
  - con una URL, usa `yt-dlp -x --audio-format mp3 -o ...` (si falta, dice `sudo apt install
    yt-dlp`). La URL **siempre** la da el usuario.
- `ultron musica silenciar|reproducir|estado`.
- `ultron tema importar <carpeta> [--modo X]`: copia `fondo.*`, `iconos/`, `sonidos/`,
  `musica.mp3` y `emblema.png` a la carpeta de datos del modo del usuario
  (`~/.local/share/ultron/modos/<id>/tema/`), que tiene prioridad sobre la del paquete.
  `registro.py` resuelve los recursos mirando primero en los datos del usuario y luego en
  el paquete.

## Criterios de aceptación
- Tests para cada capa:
  - `capturar` → `aplicar` → `restaurar`, con un EjecutorFalso que simula gsettings con un
    diccionario, y el estado final idéntico al inicial;
  - generación del GTK CSS y del CSS del shell a partir de una paleta;
  - generador de iconos con un tema base falso de 3 iconos (PNG y SVG): recoloreado,
    emblema, personalizados, `index.theme` y caché;
  - bloque de `/etc/hosts` idempotente;
  - extensiones no instaladas → la capa se salta;
  - música: se silencia, el flag persiste y se borra al entrar.
- `ultron entrar gaming --simular` en Windows lista todas las operaciones de todas las capas
  sin errores.
