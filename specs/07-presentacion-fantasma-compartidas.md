# Bloque 07: modos PRESENTACIÓN y FANTASMA, funciones compartidas y selector

## Modo PRESENTACIÓN
**Estética:** escenario de teatro, limpio, para compartir la pantalla.
- **escritorio:** fondo **generado** con un telón rojo oscuro y un foco de luz cálido en el
  centro (degradado radial en Pillow); esquema claro u oscuro según cfg; dock oculto
  (`autohide`), sin iconos en el escritorio (si está la extensión `ding`, se desactiva),
  cursor **grande** (48) y escala de texto de 1,15.
- **sistema:** no molestar (`show-banners=false`), sin suspensión ni bloqueo de pantalla
  (`idle-delay 0`, `lock-enabled false`) y sin luz nocturna.
- **terminal:** fuente grande (16) y alto contraste.
- **sonido:** "aplauso" sintético corto al entrar (ruido filtrado con envolvente) y
  silencio después.

**Funciones:**
- **`ultron diapos <archivo.md>`:**
  - presentación a pantalla completa en la terminal (Textual): diapositivas separadas por
    `---`;
  - títulos en letras grandes ASCII (fuente de bloques de 5 líneas incluida en el código),
    viñetas que aparecen una a una con `espacio`, bloques de código con resaltado (Rich
    Syntax) y transiciones (cortina, deslizar o fundido, con caracteres);
  - notas del orador después de `???`, que se ven en otra ventana con `ultron diapos
    --notas` (sincronizada por un archivo de estado);
  - número de diapositiva y temporizador abajo. `--exportar html` genera un HTML
    autocontenido.
- **`ultron ensayo <archivo.md>`:** la IA actúa como público: hace 3 preguntas difíciles
  por diapositiva y valora la claridad. `--tiempo 10` reparte los minutos por
  diapositiva según su contenido.
- **`ultron cronometro [--min 10]`:** cuenta atrás gigante a pantalla completa que cambia de
  color (verde, ámbar y rojo) a los 2 minutos y a los 30 segundos.
- **`ultron teleprompter <archivo>`:** texto grande que se desplaza, con la velocidad
  ajustable con flechas y la opción de espejo.

**IA:** "Eres ULTRON en modo PRESENTACIÓN: un coach de oratoria. Directo, motivador, con
consejos concretos de estructura, tiempos y lenguaje corporal."

## Modo FANTASMA (privacidad)
**Estética:** fantasmal y monocroma.
- **escritorio:** fondo **generado** con niebla (ruido Perlin o valor suavizado en Pillow,
  gris sobre negro) y una silueta difusa; esquema oscuro, iconos monocromo gris claro con
  un 60 % de opacidad (alpha en el generador), cursor blanco fino, animaciones lentas y
  tema GTK y del shell en negro con texto gris hueso.
- **shell:** `historial: false` (`HISTFILE=/dev/null`) y prompt `◌ anónimo`. Sin
  bienvenida ruidosa: una frase susurrada.
- **sistema:** `org.gnome.desktop.privacy`: `remember-recent-files=false`,
  `remove-old-temp-files=true`, `remove-old-trash-files=true`, `old-files-age=1`,
  `report-technical-problems=false`, `send-software-usage-stats=false`; además
  `org.gnome.desktop.search-providers disable-external=true` y ubicación desactivada
  (`org.gnome.system.location enabled=false`). Todo restaurable.

**Funciones:**
- **`ultron mac [aleatoria|restaurar|estado]`:** MAC aleatoria con NetworkManager
  (`nmcli connection modify <con> wifi.cloned-mac-address random` o
  `ethernet.cloned-mac-address random` y reactivar la conexión). Guarda la configuración
  anterior y la restaura. Avisa de que la conexión se corta unos segundos.
- **`ultron dns-seguro [on|off]`:** DNS sobre TLS con systemd-resolved (archivo
  `/etc/systemd/resolved.conf.d/99-ultron.conf` con `DNS=1.1.1.1#cloudflare-dns.com
  9.9.9.9#dns.quad9.net` y `DNSOverTLS=yes`, seguido de `systemctl restart
  systemd-resolved`). Verificación con `resolvectl status`.
- **`ultron tor [on|off|estado|navegador]`:** arranca el servicio `tor` y comprueba
  `https://check.torproject.org/api/ip` a través de `socks5://127.0.0.1:9050` (httpx con
  socks si está disponible, o `torsocks curl`). `navegador` lanza Tor Browser si está
  instalado (`torbrowser-launcher`).
- **`ultron rastros [--simular]`:** borra los rastros locales **con confirmación y una
  lista previa del tamaño de cada cosa**: archivos recientes (`recently-used.xbel`),
  miniaturas (`~/.cache/thumbnails`), historial de bash del usuario, papelera, caché de
  apt (sudo, opcional) y logs del usuario en journal (`journalctl --user --vacuum-time=1s`).
  Nunca toca documentos.
- **`ultron limpiar-meta <archivo|carpeta>`:** quita los metadatos con `mat2` si existe; si
  no, Pillow (reescribe la imagen sin EXIF) y pypdf (vacía la información del PDF). Muestra
  antes y después.
- **`ultron cofre [crear|abrir|cerrar|cifrar|descifrar]`:**
  - `cifrar` y `descifrar` de archivos con `age` (si existe) o `gpg --symmetric`;
  - `cofre crear` hace una carpeta cifrada con `gocryptfs` si existe (si no, un tar
    cifrado);
  - `abrir` la monta en `~/Cofre` y `cerrar` la desmonta.
- **`ultron efimero`:** crea `/tmp/ultron-efimero-XXXX` (en tmpfs) y abre una shell dentro;
  al salir, lo borra todo de forma segura (`shred -u` en los archivos).
- **`ultron nota-efimera`:** nota que se autodestruye: se escribe, se cifra en memoria y se
  borra al cerrarla o pasados N minutos.

**IA:** "Eres ULTRON en modo FANTASMA: susurras. Eres experto en privacidad y en seguridad
operacional. Recomiendas siempre la opción más privada y recuerdas que, para la máxima
privacidad, la IA debería ser local." Si el proveedor no es local, al primer uso en este
modo se avisa de que las preguntas salen a internet.

## Funciones compartidas (`ultron/compartidas/`)
`ordenar` está en el bloque 05. El resto:
- **`ultron haz "<petición>"`:** de lenguaje natural a comandos de Ubuntu. Usa el mismo motor
  seguro que `hackia` (muévelo a `compartidas/agente_cmd.py` y haz que `hackia` lo
  reutilice con otra personalidad): JSON de pasos, bloqueo de patrones peligrosos y
  confirmación paso a paso.
- **`ultron explica-cmd "<comando>"`:** separa el comando (con `shlex`), explica cada parte
  (la IA, y sin IA lo que dé `man -f`/`--help`) con colores por parte y un nivel de peligro.
- **`ultron error`:** recupera el último comando fallido y su salida. La capa `shell` añade
  una función bash `ultron_capturar` en `PROMPT_COMMAND` que guarda el último comando y su
  código en `~/.local/state/ultron/ultimo_cmd`, y el alias `uerr` vuelve a ejecutarlo
  capturando la salida. La IA lo diagnostica y propone el arreglo.
- **`ultron notas [nueva|lista|ver|buscar|borrar]`:** notas en Markdown en
  `~/.local/share/ultron/notas/` con frontmatter (fecha y etiquetas); `nueva "texto"` rápida
  o con `$EDITOR`; `buscar` en el texto.
- **`ultron tareas [añadir|lista|hecha|borrar]`:** con fecha, prioridad y etiqueta, guardadas
  en `tareas.json`; vista por hoy, esta semana y después; las pendientes se ven en el
  prompt `{extra}` en focus.
- **`ultron buscar "<consulta>" [carpeta]`:** busca en el contenido (txt, md, pdf, docx y
  código) con el BM25 de focus. Índice incremental en caché por la fecha de modificación.
  `--ia` reformula la consulta y resume los resultados.
- **`ultron sistema`:** resumen del sistema (distro, kernel, CPU, RAM, disco, red, batería y
  tiempo encendido) en un panel con el tema del modo.
- **Atajo global para cambiar de modo:** `ultron instalar` registra un atajo personalizado
  (`org.gnome.settings-daemon.plugins.media-keys custom-keybindings`) con **Super+U**, que
  abre una terminal con `ultron` (el selector). Es reversible en `desinstalar`.
- **`ultron bienvenida`:** ya existe; añade una frase aleatoria de la voz del modo.

## Selector (`ui/selector.py`, Textual) — `ultron` sin argumentos
- Pantalla completa con **una carta por modo** en fila (en columna si la pantalla es
  estrecha). Cada carta tiene el banner compacto, el lema y 4 funciones estrella, y se pinta
  con los colores **de su modo**.
- Las flechas mueven la selección y cambian la **paleta de fondo de toda la pantalla** a la
  del modo seleccionado, con una transición animada de unos 300 ms.
- `Enter` entra en el modo (sale del selector y lanza `motor.entrar` con la pantalla de
  carga), `s` sale del modo activo, `d` lanza `doctor`, `i` lanza `ia chat` y `q` sale.
- El modo activo lleva una insignia `● ACTIVO`.
- Abajo, una barra con el estado de la IA (`● IA: llama3.2 @ localhost` en verde, o
  `○ IA sin configurar · pulsa c`) y `c` abre `ia configurar`.
- Animación de arranque: un logo ULTRON que se arma con caracteres aleatorios.

## Criterios de aceptación
- Tests:
  - diapos: el parser de Markdown en diapositivas, las notas y el reparto del tiempo;
  - la fuente de letras grandes;
  - mac: los comandos de nmcli y su restauración;
  - dns-seguro: el archivo generado y su restauración;
  - rastros: la lista previa y que nunca toca rutas fuera de la lista;
  - limpiar-meta: una imagen con EXIF queda sin EXIF;
  - cofre: los comandos de age y gpg;
  - haz y hackia: el motor compartido y el bloqueo;
  - explica-cmd: la división en partes;
  - notas, tareas y buscar;
  - el selector con el `Pilot` de Textual: navegación, Enter llama a entrar (motor
    falseado) y q sale.
