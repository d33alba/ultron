# Ultron: plan del proyecto

CLI en Python para Ubuntu. Eliges un **modo** y el sistema operativo se transforma por
completo, como si fuera otro sistema: fondo, iconos (apps, carpetas y archivos), tema de
ventanas, cursor, sonidos, terminal, animaciones, arranque y una IA con personalidad propia.
No se quita ninguna funcionalidad: solo cambia todo lo estético que se puede cambiar.
`ultron salir` lo deshace todo.

**Entrega:** en una semana (hacia el 3-12-2026). El profesor lo prueba **en su Ubuntu**, con
**una API de IA local** y a través de **un GitHub organizado**. Valora la **creatividad** y las
**funcionalidades**.

```
ultron                     # selector de modos a pantalla completa, animado
ultron entrar <modo>       # transformar el sistema (con pantalla de carga)
ultron salir               # deshacer todos los cambios estéticos
ultron estado              # modo activo y capas aplicadas
ultron ia "pregunta"       # IA del modo activo
ultron ia configurar       # proveedor, URL, modelo y clave, con prueba incluida
ultron doctor              # diagnóstico: sistema, dependencias, archivos del tema, IA
ultron instalar            # instalación única de dependencias y extensiones (pide sudo)
```

---

## Modo NETANYAHU: hacker israelí

### Estética: todo el sistema
- **Fondo:** Netanyahu generado con GPT Images, también para la pantalla de bloqueo.
- **Iconos:** tema completo con la bandera israelí (azul `#0038B8` y blanco): carpetas,
  archivos de cada tipo, apps, papelera, dispositivos.
  - **Todos los iconos**, del orden de miles, se generan **con un script**: recolorea el tema
    Yaru de Ubuntu (licencia CC-BY-SA, con atribución) a la paleta israelí y añade la estrella
    de David en las carpetas. Sale gratis, es coherente y no se deja ninguno.
  - **Iconos estrella** hechos con GPT Images: Firefox, Archivos, Terminal, Ajustes,
    Calculadora, Software, Texto, Visor de imágenes, Música, Papelera (unos 10–15).
- **Tema de ventanas y shell:** GTK y barra superior en azul y blanco, con acentos azules.
- **Cursor:** azul y blanco, con la estrella al hacer clic.
- **Terminal:** perfil azul y blanco, más la interfaz de Ultron diseñada en
  `specs/diseno-terminal.md`.
- **Sonido:** al entrar suena la música de Netanyahu (flauta). Aparece un **icono de bocina
  en la esquina** de la barra superior: al pulsarlo se silencia la música y el icono
  desaparece. Queda silenciada hasta que se vuelve a entrar en el modo.
- **Arranque:** pantalla de carga (Plymouth) y pantalla de inicio de sesión con la estética.

### Funciones de hacker
**OSINT** (solo información pública):
- `ultron osint dominio`: whois, DNS, subdominios (certificados de crt.sh), tecnologías web
  y cabeceras de seguridad
- `ultron osint ip`: geolocalización, ASN y puertos públicos
- `ultron osint usuario`: busca un nombre de usuario en unas 100 webs públicas
- `ultron osint meta`: metadatos EXIF y GPS de fotos y documentos, con mapa ASCII
- `ultron osint correo`: análisis de cabeceras (ruta, SPF, DKIM, posible suplantación)
- `ultron osint informe`: la IA junta todo lo anterior en un informe en Markdown o PDF

**Hacking ético** (en tu red, en tu equipo o en objetivos autorizados; la IA lo explica todo):
- `ultron radar`: mapa ASCII en vivo de los dispositivos de tu red local (nmap y ARP), con
  fabricante y puertos
- `ultron auditar`: auditoría de seguridad del propio Ubuntu (lynis, puertos abiertos,
  servicios, actualizaciones pendientes); la IA da una nota y cómo arreglar cada punto
- `ultron cve`: busca vulnerabilidades conocidas en los paquetes instalados
- `ultron filtrado`: comprueba si una contraseña aparece en filtraciones (Have I Been Pwned
  con k-anonimato: la contraseña nunca sale del equipo)
- `ultron web`: análisis de seguridad de una web propia (SSL, cabeceras, archivos expuestos)
- `ultron ctf`: navaja suiza para retos: codificar y decodificar, identificar hashes,
  esteganografía, `strings` y binwalk
- `ultron hackia "qué quiero hacer"`: la IA traduce lo que pides a comandos de Ubuntu,
  enseña qué hace cada uno y los ejecuta solo si confirmas

**Ojo de Dios:** pendiente de saber qué es exactamente (ver dudas).

### IA
Analista de inteligencia: directa, técnica y en tono de operación.

---

## Modo FOCUS: estudio

### Estética
Limpia y de concentración. Tonos neutros, sin animaciones, notificaciones desactivadas,
fondo minimalista, iconos planos en gris, barra superior mínima y tipografía legible.

### Funciones
- **PDF y apuntes:**
  - `ultron resumen archivo.pdf`: resumen por niveles (una línea, un párrafo o esquema completo)
  - `ultron flashcards archivo.pdf`: genera tarjetas y las exporta a Anki (`.apkg`)
  - `ultron repasar`: repaso de tarjetas en la terminal con repetición espaciada (SM-2)
  - `ultron examen archivo.pdf`: examen tipo test o de respuesta corta, con nota y correcciones
  - `ultron pregunta archivo.pdf "duda"`: preguntas sobre el PDF, con la página donde está
    la respuesta
  - `ultron esquema archivo.pdf`: mapa conceptual en ASCII, exportable a imagen
  - `ultron explica "concepto"`: explicación a tres niveles (simple, normal y experto)
- **Organización:**
  - `ultron plan`: le das los exámenes y entregas, y crea un plan de estudio día a día con
    cuenta atrás
  - `ultron pomodoro`: temporizador en la barra superior y en el prompt; bloquea webs de
    distracción mientras dura
  - `ultron stats`: horas estudiadas por asignatura y racha de días seguidos, con un mapa de
    calor estilo GitHub

### IA
Tutor paciente: explica, pregunta y comprueba que lo has entendido.

---

## Modo GAMING: cyberpunk

### Estética
Que no parezca Ubuntu. Hiperfuturista, neón y animado.
- **Ventanas animadas:** Burn My Windows (efectos de fuego, glitch o TV al abrir y cerrar),
  ventanas gelatinosas (Compiz Windows Effect) y cubo 3D entre escritorios (Desktop Cube).
- **Shell:** cristal desenfocado (Blur my Shell), barra superior neón (Open Bar), dock
  flotante y esquinas redondeadas.
- **Fondo animado** en vídeo (extensión Hanabi) con una ciudad cyberpunk en bucle.
- **Widgets de escritorio:** Conky con reloj, CPU, GPU, red y temperatura en estilo HUD.
- **Visualizador de música** cava en la terminal.
- **Tema GTK** neón, **iconos** recoloreados en magenta y cian con brillo, **cursor** neón
  (Bibata) y **fuentes** Orbitron y JetBrains Mono Nerd.
- **Sonidos de sistema** futuristas y **arranque** con un Plymouth cyberpunk y un tema de GRUB.

### Funciones gaming útiles
- `ultron juegos`: biblioteca unificada (Steam, Lutris, Flatpak y nativos) con portadas en la
  terminal; lanza con un número
- `ultron turbo`: modo rendimiento (GameMode, gobernador de CPU, pausa de servicios que no
  hacen falta y de la indexación); se desactiva al salir
- `ultron hud`: panel en vivo de CPU, GPU, RAM, temperaturas y red, como un HUD
- `ultron fps`: activa MangoHud en los juegos lanzados desde Ultron
- `ultron clip`: graba los últimos 30 segundos de pantalla con un atajo
- XP, niveles y logros por usar Ultron

### IA
Compañero gamer: trucos, guías de juegos y configuración de rendimiento.

---

## Funciones compartidas (en todos los modos)

- `ultron ordenar <carpeta>`: la IA mira cada archivo (nombre, tipo y contenido de PDF y
  documentos), propone una estructura de carpetas (crea las que falten), **enseña el plan
  antes de moverlos** y permite deshacerlo con `ultron ordenar --deshacer`
- `ultron haz "lo que quieres"`: de lenguaje natural a comandos de Ubuntu, que se ejecutan
  solo si confirmas
- `ultron explica-cmd "comando"`: explica un comando trozo a trozo
- `ultron error`: la IA lee el último error de la terminal y propone cómo arreglarlo
- `ultron notas` y `ultron tareas`: rápidas, guardadas en Markdown
- `ultron buscar "algo"`: busca archivos por lo que contienen, no solo por el nombre
- `ultron sistema`: monitor del sistema con la estética del modo
- Atajo de teclado global para cambiar de modo

---

## IA modular (requisito de la entrega)

- **Sin modelo incluido.** El profesor usará una IA local, casi seguro con una API compatible
  con OpenAI (Ollama, LM Studio, vLLM, llama.cpp).
- **Adaptadores:** `openai-compatible` (cubre el caso local y también OpenAI, Groq,
  OpenRouter y Gemini) y `anthropic`.
- **Configuración:** `ultron ia configurar` (asistente), variables de entorno
  `ULTRON_URL_BASE`, `ULTRON_MODELO` y `ULTRON_API_KEY` (opcional en local), o el archivo
  `~/.config/ultron/config.toml`.
- **Detección automática:** si encuentra Ollama o LM Studio en el equipo, los propone y
  lista sus modelos.
- **Pensado para modelos locales pequeños:**
  - prompts cortos
  - los PDF largos se trocean y se resumen por partes
  - las respuestas en JSON se reparan si llegan mal formadas
  - tiempos de espera largos, con streaming para que se vea avanzar
- **`ultron doctor`** prueba la conexión real y explica cada error en español: no responde,
  URL mal puesta, modelo inexistente, clave incorrecta o contexto demasiado largo.
- **Sin IA, todo lo que no es de IA sigue funcionando.**
- **Pruebas:** servidor falso en los tests y prueba real con Ollama antes de entregar.

---

## Arquitectura

`modos/<modo>/` con `modo.yaml` (capas, IA y funciones), `tema/` (recursos) y `funciones/`.

**Capas** (cada una sabe aplicar, guardar el estado anterior y restaurar):
`shell`, `terminal`, `escritorio`, `iconos`, `cursor`, `fuentes`, `extensiones`, `sonido`,
`musica`, `widgets`, `sistema`, `arranque`.

**Extensión de GNOME propia, `ultron@ultron`:** indicador en la barra superior con el modo
activo, el botón de bocina para silenciar, el pomodoro y la XP.

**Instalación en dos tiempos (por Wayland):** en Ubuntu con Wayland, una extensión de GNOME
nueva no carga hasta que cierras sesión.
1. `ultron instalar` se ejecuta una sola vez: instala dependencias, extensiones y temas, y
   pide cerrar sesión una vez.
2. Después, cambiar de modo **solo activa y desactiva** lo que ya está instalado, en directo
   y sin cerrar sesión.

**Pantalla de carga:** mientras se aplican las capas se ve una animación del modo a pantalla
completa (GTK), con la terminal como alternativa.

**Seguridad:** instantánea antes de cada cambio, `ultron salir` restaura aunque algo falle a
medias, `--simular` enseña los cambios sin hacerlos y `sudo` solo con aviso previo.

**Compatibilidad:** pensado para Ubuntu 24.04 (GNOME 46); también 24.10 y 25.04. `doctor`
avisa si algo no es compatible y esa capa se salta sin romper el resto.

---

## Recursos que no genera el código

| Recurso | Quién lo hace | Dónde va |
|---|---|---|
| Fondo de Netanyahu | David, con GPT Images (prompt en `specs/prompts-imagenes.md`) | `modos/netanyahu/tema/fondo.png` |
| 10–15 iconos estrella israelíes | David, con GPT Images (mismos prompts) | `modos/netanyahu/tema/iconos/` |
| Música de flauta | David | `modos/netanyahu/tema/musica.mp3` |
| Fondo de vídeo cyberpunk | Vídeo libre de derechos (Pexels o Pixabay) | `modos/gaming/tema/fondo.mp4` |
| Todos los demás iconos | Script automático | se generan al instalar |

---

## Forma de trabajar (rápida y sin malgastar tokens)

1. Claude escribe una especificación **completa** por bloque en `specs/`, con criterios de
   aceptación y tests.
2. Codex la implementa en una sola pasada no interactiva (`codex exec --full-auto`).
3. Los tests se pasan solos: aquí en Windows lo que es lógica, y **en Ubuntu real con GitHub
   Actions** en cada push.
4. Claude revisa solo lo que falla y lanza correcciones concretas.
5. Lo visual se comprueba en una **VM de Ubuntu (Hyper-V Quick Create)**, con capturas.
6. Cuando se acaben los tokens de GPT, Claude sigue implementando.

## Calendario (7 días)

| Día | Bloque |
|---|---|
| 1 | Repo de GitHub y CI; esqueleto, motor de modos y capas, IA modular, `doctor`; preparar la VM |
| 2 | Capas visuales, generador de iconos, extensión `ultron@ultron`, pantalla de carga |
| 3 | NETANYAHU completo: tema, música con bocina, OSINT y hacking ético |
| 4 | FOCUS completo: PDF, flashcards, exámenes, plan, pomodoro, estadísticas |
| 5 | GAMING completo: extensiones, widgets, fondo animado, juegos, turbo, HUD |
| 6 | Funciones compartidas, arranque (Plymouth, GRUB, GDM), selector animado, instalador |
| 7 | Prueba en una VM limpia como la del profesor, README con GIFs, entrega |

## Estructura del GitHub

```
ultron/
├── README.md            # qué es, GIFs de cada modo, instalación en 3 comandos
├── docs/                # manual de cada modo, configuración de la IA, arquitectura
├── ultron/              # código (núcleo, capas, ia, ui, compartidas)
│   └── modos/           # netanyahu/ focus/ gaming/ presentacion/ fantasma/
├── extension/           # extensión de GNOME ultron@ultron
├── scripts/             # instalador y generador de iconos
├── tests/
├── specs/               # especificaciones de cada fase
└── .github/workflows/   # CI en Ubuntu
```
