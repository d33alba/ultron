# Bloque 04: modo NETANYAHU (hacker israelí)

## Objetivo
El modo más espectacular. El sistema entero con estética israelí (azul `#0038B8`, blanco,
estrella de David) y funciones de OSINT y hacking ético que de verdad funcionan y quedan
impresionantes en la terminal. Todo con la interfaz de "operación de inteligencia" de
`specs/diseno-terminal.md`.

## `modo.yaml` completo
- **shell:** el prompt del diseño, `{extra}` con la operación actual y alias `op`, `objetivo`.
- **terminal:** fondo `#0A1A3F`, texto `#FFFFFF`, paleta azul y blanca (los "verdes" de ANSI
  se cambian por azules claros, para que todo cuadre), cursor de bloque blanco, fuente
  JetBrains Mono y transparencia del 8 %.
- **escritorio:**
  - fondo `tema/fondo.png` (si falta, se usa un fondo **generado** por
    `ultron/modos/netanyahu/generar_fondo.py` con Pillow: degradado azul marino, las dos
    franjas de la bandera, estrella de David grande con brillo, una rejilla de "radar" y
    el texto "ULTRON // NETANYAHU");
  - esquema oscuro, acento azul, tema GTK y tema del shell generados;
  - dock abajo, centrado, con fondo azul `#0038B8` al 85 %.
- **iconos:** base Yaru, tinte hacia `#0038B8` con intensidad 0,85, emblema
  `tema/emblema.png` (estrella de David blanca con borde azul, generada con Pillow si
  falta) en `places`, y los personalizados de `tema/iconos/`.
- **cursor:** generado en azul y blanco, tamaño 32.
- **sonido:** tema con `entrada.oga` (un pitido de teletipo, **generado** de forma
  sintética con numpy o la librería estándar `wave` y convertido a ogg con ffmpeg si existe;
  si no, se usa el `.wav`) y los sonidos de notificación y de error.
- **musica:** `tema/musica.mp3`, en bucle, al 70 %, con un fundido de entrada de 2 s.
- **widgets:** Conky con "RADAR STATUS": hora de Jerusalén y local, IP pública y local,
  dispositivos en la red (número del último `ultron radar`), CPU y RAM, en azul y blanco.
- **extensiones:** `user-theme` y `blur-my-shell` (con un desenfoque suave), y
  `burn-my-windows` con el efecto "TV" o "Glitch" en azul.
- **sistema:** nada agresivo.
- **arranque:** Plymouth con la estrella de David que se dibuja (animación del script de
  Plymouth con fotogramas generados) y el texto "ULTRON"; GRUB y GDM con el fondo.
- **dependencias:** apt `nmap`, `whois`, `dnsutils`, `lynis`, `exiftool`
  (`libimage-exiftool-perl`), `binwalk`, `steghide`, `john`, `hashid`, `git`,
  `nodejs`/`npm` (comprueba la versión ≥ 24; si no, ofrece instalarla con nvm o `n`) y
  `traceroute`.
- **recursos_opcionales:** `tema/fondo.png` (Netanyahu, GPT Images), `tema/musica.mp3`
  (`ultron musica importar <url>`) y `tema/iconos/*` (iconos estrella).

## Generadores de recursos (en el repo, sin derechos de autor)
`ultron/modos/netanyahu/generar_recursos.py` con el comando oculto `ultron netanyahu
generar-recursos`: crea el fondo por defecto, el emblema, la estrella para Plymouth
(fotogramas), los sonidos y el logo. Se llama desde `ultron instalar --modo netanyahu` y
cuando falte algún recurso.

## Funciones OSINT (`ultron osint ...`)
Todas en paneles `DOUBLE` con título `✡ INFORME …`, con spinner de "operación",
`--json` para sacar los datos crudos y guardado en
`~/.local/share/ultron/operaciones/<fecha>-<objetivo>/`.

- **`osint dominio <d>`:**
  - whois (comando `whois`, o socket al servidor whois de IANA y luego al de la TLD);
  - DNS con dnspython (A, AAAA, MX, NS, TXT, SOA y CAA), SPF y DMARC;
  - subdominios desde `https://crt.sh/?q=%25.<d>&output=json` (deduplicados);
  - HTTP: título, servidor, tecnologías detectadas por cabeceras y HTML (unas 30 firmas:
    WordPress, nginx, Cloudflare, React…) y cabeceras de seguridad con nota A–F;
  - certificado TLS (emisor, caducidad).
- **`osint ip <ip>`:** geolocalización (`http://ip-api.com/json/<ip>`; sin clave), ASN, ISP,
  DNS inverso, si es Tor o proxy (si lo da la API) y un **mini mapa del mundo en ASCII** con
  la posición marcada `◉` (mapa equirectangular de unas 70×20 en un archivo de datos).
- **`osint usuario <nombre>`:** comprueba unas 80 webs públicas definidas en
  `datos/sitios.json` (url, método de comprobación por código o por texto). Concurrente
  con `httpx.AsyncClient` (límite de 20) y un timeout de 8 s; tabla con los encontrados y
  sus enlaces.
- **`osint meta <archivo>`:** EXIF con Pillow (cámara, fecha, software, GPS → coordenadas
  decimales + enlace a OpenStreetMap + punto en el mapa ASCII), metadatos de PDF con pypdf
  y, si existe `exiftool`, todo lo que dé `exiftool -j`.
- **`osint correo <archivo.eml>`:** ruta de saltos `Received` con IP y fecha, From,
  Return-Path y Reply-To (con aviso si no coinciden), y resultados de SPF, DKIM y DMARC de
  `Authentication-Results`. La IA da un veredicto de posible phishing (si hay IA).
- **`osint informe <carpeta-operacion>`:** la IA redacta un informe en Markdown (resumen
  ejecutivo, hallazgos, riesgos y recomendaciones) y, si hay `pandoc`, lo exporta a PDF.

## Hacking ético
Avisos: la primera vez se muestra un panel rojo "Solo en tu red, tu equipo o con permiso
escrito" que se acepta una vez y queda guardado en config.

- **`ultron radar [--continuo] [--red 192.168.1.0/24]`:**
  - detecta la red (`ip route`); `nmap -sn` (con sudo para obtener MAC y fabricante, si se
    acepta) o la tabla ARP (`ip neigh`) como respaldo;
  - **visualización en radar ASCII**: un círculo con un barrido animado (una línea que gira
    con estela de `░▒▓`), cada dispositivo como `◉` con la etiqueta a una distancia y un
    ángulo deterministas (hash de la MAC), tu equipo en el centro `✡` y el router
    destacado;
  - una tabla al lado con IP, MAC, fabricante y nombre;
  - `--puertos` lanza `nmap -F` en cada uno;
  - en `--continuo` refresca cada 10 s y marca **NUEVO** el que aparece. Usa Rich Live.
- **`ultron auditar`:** puertos en escucha (`ss -tulpn`), servicios activos, cortafuegos
  (`ufw status`), actualizaciones pendientes, usuarios con shell, SSH (`PermitRootLogin`,
  `PasswordAuthentication`) y, si existe, `lynis audit system --quick` (lo procesa). Nota
  global de 0 a 100 con una barra y la lista ordenada por gravedad. La IA explica cómo
  arreglar cada punto (con comandos exactos que **no** se ejecutan solos).
- **`ultron cve [paquete]`:** lista los paquetes instalados (`dpkg-query`) y consulta la API
  de OSV (`https://api.osv.dev/v1/querybatch`, ecosistema `Ubuntu:24.04:LTS`, o Debian como
  respaldo). Tabla con CVE, gravedad y la versión corregida.
- **`ultron filtrado`:** pide la contraseña oculta, calcula el SHA-1, consulta
  `https://api.pwnedpasswords.com/range/<5 primeros>` y compara localmente. Muestra cuántas
  veces aparece. **La contraseña ni el hash completo salen del equipo ni se guardan.**
- **`ultron web <url>`:** cabeceras de seguridad, TLS (versión, caducidad, cifrado), rutas
  expuestas típicas (`/.git/HEAD`, `/.env`, `/server-status`, `/robots.txt`,
  `/sitemap.xml`, `/wp-login.php`, unas 20 solo con GET) y `security.txt`. Aviso de que es
  solo para webs propias o con permiso.
- **`ultron ctf`:** subcomandos:
  - `decodificar <texto>`: prueba automáticamente base64/32/85, hex, binario, rot13, URL,
    morse y cifrado César con las 25 rotaciones, y marca la más probable por frecuencia de
    letras en español e inglés;
  - `codificar <tipo> <texto>`;
  - `hash <hash>`: identifica el tipo por longitud y patrón; `hashid` si existe;
  - `crackear <hash> [--lista rockyou]`: `john` si existe; si no, un diccionario pequeño
    integrado;
  - `estego <archivo>`: `strings`, `binwalk`, `steghide info` y el LSB de imágenes con Pillow;
  - `archivo <f>`: tipo real por los magic bytes, entropía, y `strings` con las cadenas
    interesantes (URLs, flags `flag{…}`).
- **`ultron hackia "<qué quieres hacer>"`:**
  - la IA (con personalidad de analista y un prompt que **exige** JSON `{explicacion,
    pasos:[{comando, que_hace, peligro: bajo|medio|alto}]}`) propone comandos de Ubuntu;
  - se muestran en una tabla y se confirma **uno por uno** (`s/n/todos/editar`);
  - bloqueo duro de patrones destructivos (`rm -rf /`, `mkfs`, `dd of=/dev/sd`, fork bomb,
    `chmod -R 777 /`, descargas encadenadas a `sh`);
  - se ejecutan con el Ejecutor y la salida se devuelve a la IA para el siguiente paso
    (bucle de 5 pasos como mucho).

## Ojo de Dios (`ultron ojo`)
Integra **God's Eye View** (https://github.com/bilawalsidhu/gods-eye-view, licencia MIT): un
globo 3D con aviones, barcos, satélites, terremotos y cámaras en tiempo real.
- **`ultron ojo instalar`:**
  - comprueba `git` y Node ≥ 24.14 (si no, explica cómo instalar Node 24 con
    `nvm`/NodeSource y lo ofrece);
  - `git clone --depth 1` en `~/.local/share/ultron/ojo/gods-eye-view`;
  - `npm ci` y `npm run doctor`. Muestra el progreso con el tema.
- **`ultron ojo`** (o `ultron ojo abrir`):
  - si no está instalado, lo ofrece;
  - arranca `npm run dev -- --port 4173` en segundo plano (PID y log en estado) y espera a
    que responda `http://localhost:4173`;
  - abre el navegador con `xdg-open` (con `--kiosko`, `firefox --kiosk`).
  - Antes enseña una animación de "ESTABLECIENDO ENLACE SATELITAL" con la estrella y un
    globo ASCII girando (unos 10 fotogramas precalculados de un globo con meridianos).
- `ultron ojo parar`, `ultron ojo actualizar` (`git pull` + `npm ci`) y `ultron ojo estado`.
- `ultron ojo objetivo <lugar|lat,lon>`: abre la URL con la cámara en esas coordenadas,
  usando el formato de enlaces para compartir que documenta el README del repo (consúltalo
  en `docs/` del repo clonado cuando esté instalado; si no se encuentra el formato, abre la
  app sin parámetros).
- Créditos y licencia del proyecto en `docs/modos/netanyahu.md`.

## IA del modo
"Eres ULTRON en modo NETANYAHU: analista jefe de una unidad de ciberinteligencia israelí.
Hablas como en un informe de operaciones: frases cortas, precisas y técnicas. Usas términos
como OBJETIVO, VECTOR y SUPERFICIE. Enseñas hacking ético y OSINT, siempre dentro de la ley:
si te piden atacar a terceros sin permiso, te niegas y propones una alternativa legal (un
laboratorio, un CTF)."

## Criterios de aceptación
- Tests con la red falseada (`httpx.MockTransport`/respx-like):
  - dominio: DNS falseado con un resolver inyectable, y crt.sh;
  - ip: el punto en el mapa ASCII en la posición correcta para 3 coordenadas;
  - usuario: concurrencia y los dos métodos de comprobación;
  - meta: EXIF con GPS de una imagen generada en el test;
  - correo: un `.eml` de ejemplo con SPF fail;
  - radar: procesado de la salida de `nmap -sn` y de `ip neigh`, y la posición determinista
    en el radar;
  - auditar: el cálculo de la nota a partir de hallazgos falseados;
  - filtrado: solo se envían 5 caracteres y la comparación es local;
  - ctf: decodificar con 10 casos, incluido César;
  - hackia: bloqueo de patrones peligrosos, y nada se ejecuta sin confirmación;
  - ojo: comprobación de la versión de Node, y los comandos de instalación y arranque en el
    historial.
- `ultron radar --demo` y `ultron osint ip 8.8.8.8 --demo` muestran resultados de ejemplo sin
  red (para el README y las capturas).
