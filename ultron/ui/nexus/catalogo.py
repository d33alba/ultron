"""Catálogo de funciones del NEXUS: cada comando de Ultron como una ficha con formulario.

El NEXUS (y los lanzadores del escritorio y la extensión del panel) leen este catálogo para que
nadie tenga que saberse la sintaxis: cada ficha dice qué hace, con qué icono se dibuja y qué
datos pide; `argv()` monta la línea de comandos a partir de lo que se rellena en el formulario.
"""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass

COMUN = "comun"


@dataclass(frozen=True)
class Campo:
    """Un dato que pide la ficha. `opcion` vacío = argumento posicional."""

    nombre: str
    etiqueta: str
    tipo: str = "texto"  # texto | archivo | carpeta | numero | si_no
    obligatorio: bool = True
    opcion: str = ""  # "--n", "--anki"… (para si_no es un interruptor)
    defecto: str = ""


@dataclass(frozen=True)
class Ficha:
    modo: str
    comando: str  # "osint dominio"
    icono: str
    titulo: str
    descripcion: str
    campos: tuple[Campo, ...] = ()
    claves: str = ""  # palabras extra para la búsqueda en lenguaje natural
    escritorio: bool = False  # se pone como lanzador en el escritorio y el dock
    soltar: str = ""  # nombre del campo que recibe un archivo soltado sobre el lanzador

    @property
    def id(self) -> str:
        return self.comando.replace(" ", "-")

    def argv(self, valores: dict[str, str] | None = None) -> list[str]:
        """Monta los argumentos de `ultron` con los valores del formulario."""
        valores = valores or {}
        args = self.comando.split()
        for c in self.campos:
            valor = str(valores.get(c.nombre, c.defecto) or "").strip()
            if c.tipo == "si_no":
                if valor.lower() in {"1", "true", "si", "sí", "on"}:
                    args.append(c.opcion)
                continue
            if not valor:
                continue
            args.extend([c.opcion, valor] if c.opcion else [valor])
        return args

    def faltan(self, valores: dict[str, str]) -> list[Campo]:
        return [c for c in self.campos if c.obligatorio and c.tipo != "si_no"
                and not str(valores.get(c.nombre, c.defecto) or "").strip()]


def A(nombre: str, etiqueta: str, tipo: str = "texto", obligatorio: bool = True,
      defecto: str = "") -> Campo:
    return Campo(nombre, etiqueta, tipo, obligatorio, "", defecto)


def O(opcion: str, etiqueta: str, tipo: str = "texto", defecto: str = "") -> Campo:  # noqa: E743
    return Campo(opcion.lstrip("-").replace("-", "_"), etiqueta, tipo, False, opcion, defecto)


def S(opcion: str, etiqueta: str) -> Campo:
    return Campo(opcion.lstrip("-").replace("-", "_"), etiqueta, "si_no", False, opcion)


DOC = A("archivo", "Documento (PDF, apuntes .md/.txt)", "archivo")

FICHAS: tuple[Ficha, ...] = (
    # ── NETANYAHU ──────────────────────────────────────────────────────────────
    Ficha("netanyahu", "ojo abrir", "◈", "OJO DE DIOS",
          "Globo terráqueo en directo: aviones, satélites, barcos y cámaras del planeta.",
          claves="mapa globo mundo aviones satelites planeta vigilancia", escritorio=True),
    Ficha("netanyahu", "osint operacion", "⊕", "Investigar objetivo",
          "Todas las fuentes a la vez sobre un dominio o IP: exposición, CVE, mapa y dossier.",
          (A("objetivo", "Dominio, IP pública o URL"),
           S("--mapa", "Situarlo en el Ojo de Dios")),
          "operacion investigar empresa web servidor infraestructura dossier objetivo",
          escritorio=True),
    Ficha("netanyahu", "radar", "◉", "Radar de red",
          "Barrido de tu red local: qué dispositivos hay conectados y quién es cada uno.",
          (S("--puertos", "Ver también los puertos abiertos"),
           S("--continuo", "Vigilar en continuo")), "red wifi dispositivos escanear lan",
          escritorio=True),
    Ficha("netanyahu", "osint huella", "☉", "Informe de huella digital",
          "Qué se sabe de ti (o de quien te lo autorice): filtraciones, alias, fotos y cómo "
          "borrarlo. Informe listo para entregar.",
          (O("--para", "Persona (vacío = tú; si es otra, debe haberlo autorizado)"),
           O("--correo", "Correo"), O("--alias", "Alias o usuario"),
           O("--nombre", "Nombre y apellidos")),
          "huella digital filtraciones exposicion privacidad informe persona",
          escritorio=True),
    Ficha("netanyahu", "osint url", "⚑", "¿Es fiable este enlace?",
          "Redirecciones, phishing, typosquatting, antigüedad y reputación de un enlace.",
          (A("enlace", "Enlace sospechoso"),), "enlace link phishing estafa sospechoso url",
          escritorio=True),
    Ficha("netanyahu", "osint imagen", "◑", "Analizar una foto",
          "GPS y cámara de la foto, y búsqueda inversa en Google Lens, Bing, Yandex y TinEye.",
          (A("origen", "Foto o URL de la imagen", "archivo"), S("--abrir", "Abrir búsquedas")),
          "foto imagen inversa origen", soltar="origen"),
    Ficha("netanyahu", "osint fuentes", "☷", "Arsenal OSINT",
          "Todas las fuentes y herramientas conectadas y cuáles puedes añadir.",
          claves="fuentes herramientas arsenal"),
    Ficha("netanyahu", "osint dominio", "⌖", "Ficha de dominio",
          "DNS, WHOIS, certificados públicos y portada web de un dominio.",
          (A("objetivo", "Dominio (p. ej. ubuntu.com)"),), "dominio dns whois"),
    Ficha("netanyahu", "osint ip", "◎", "Rastrear IP",
          "Geolocaliza una IP pública y dice a quién pertenece.",
          (A("objetivo", "Dirección IP"),), "ip localizar geolocalizar"),
    Ficha("netanyahu", "osint usuario", "◍", "Buscar alias",
          "Busca un nombre de usuario en perfiles públicos de redes sociales.",
          (A("nombre", "Nombre de usuario"),), "usuario redes sociales perfil persona"),
    Ficha("netanyahu", "osint meta", "▤", "Metadatos de archivo",
          "Saca el GPS, la cámara y el autor de una foto o documento.",
          (A("archivo", "Foto o documento", "archivo"),), "exif foto gps metadatos",
          escritorio=True, soltar="archivo"),
    Ficha("netanyahu", "auditar", "▣", "Auditar este equipo",
          "Servicios, cortafuegos, SSH y actualizaciones: tu nota de seguridad.",
          claves="seguridad auditoria proteger equipo"),
    Ficha("netanyahu", "cve", "⚠", "Vulnerabilidades (CVE)",
          "Cruza tus paquetes instalados con los avisos públicos de vulnerabilidades.",
          (A("paquete", "Paquete concreto (vacío = todos)", obligatorio=False),),
          "vulnerabilidad parche cve"),
    Ficha("netanyahu", "filtrado", "✱", "¿Contraseña filtrada?",
          "Comprueba si una contraseña aparece en filtraciones (sin enviarla nunca).",
          claves="contraseña password filtracion pwned"),
    Ficha("netanyahu", "web", "⬡", "Revisar mi web",
          "Cabeceras de seguridad y TLS de una web propia o autorizada.",
          (A("url", "URL (https://…)"),), "web cabeceras tls https"),
    Ficha("netanyahu", "ctf decodificar", "⌬", "Descifrar mensaje",
          "Prueba base64, hex, ROT13, Morse… y ordena las lecturas por probabilidad.",
          (A("texto", "Texto cifrado"),), "descifrar decodificar base64 cifrado ctf"),
    Ficha("netanyahu", "ctf hash", "#", "Identificar hash",
          "Adivina el algoritmo de una huella (MD5, SHA, bcrypt…).",
          (A("huella", "Hash"),), "hash md5 sha"),
    Ficha("netanyahu", "ctf estego", "◐", "Esteganografía",
          "Busca mensajes ocultos dentro de una imagen.",
          (A("archivo", "Imagen", "archivo"),), "oculto imagen estego", soltar="archivo"),
    Ficha("netanyahu", "hackia", "✦", "Analista IA",
          "Describe un problema de seguridad y la IA propone diagnósticos (tú apruebas cada uno).",
          (A("solicitud", "¿Qué quieres revisar?"),), "analista ayuda seguridad ia"),
    Ficha("netanyahu", "osint informe", "☰", "Informe de operación",
          "Redacta el informe de una operación guardada (y PDF si quieres).",
          (A("carpeta", "Carpeta de la operación", "carpeta"), S("--pdf", "Exportar a PDF")),
          "informe reporte"),
    # ── FOCUS ──────────────────────────────────────────────────────────────────
    Ficha("focus", "pomodoro", "◷", "Sesión de estudio",
          "Pomodoro con reloj gigante; bloquea las webs que distraen mientras dura.",
          claves="estudiar concentrar temporizador pomodoro tiempo", escritorio=True),
    Ficha("focus", "resumen", "✎", "Resumir apuntes",
          "Resume un PDF o tus apuntes por partes (funciona con modelos pequeños).",
          (DOC, S("--guardar", "Guardar el resumen junto al archivo")),
          "resumir resumen pdf apuntes tema", escritorio=True, soltar="archivo"),
    Ficha("focus", "flashcards crear", "▦", "Crear flashcards",
          "Convierte un documento en tarjetas de memoria (y en mazo de Anki).",
          (DOC, S("--anki", "Exportar también a Anki")), "tarjetas memorizar anki flashcards",
          escritorio=True, soltar="archivo"),
    Ficha("focus", "repasar", "↻", "Repasar tarjetas",
          "Repetición espaciada: solo te pregunta lo que toca hoy.",
          claves="repasar memorizar tarjetas", escritorio=True),
    Ficha("focus", "examen", "✓", "Examen de prueba",
          "Genera un examen de tu documento, lo corrige y te pone nota.",
          (DOC, O("--n", "Número de preguntas", "numero", "10")), "examen test preguntas nota",
          escritorio=True, soltar="archivo"),
    Ficha("focus", "pregunta", "?", "Preguntar al documento",
          "Resuelve una duda sobre tus apuntes citando la página.",
          (DOC, A("duda", "Tu duda")), "duda pregunta pdf"),
    Ficha("focus", "explica", "✧", "Explícame algo",
          "Un concepto explicado a tres niveles, con ejemplo y pregunta de control.",
          (A("concepto", "Concepto"),), "explicar entender concepto"),
    Ficha("focus", "esquema", "⋔", "Mapa conceptual",
          "Árbol de ideas del documento (también en PNG).",
          (DOC,), "esquema mapa conceptual", soltar="archivo"),
    Ficha("focus", "plan hoy", "☀", "Qué toca hoy",
          "Lo que tienes que estudiar hoy según tus exámenes.", claves="hoy plan estudiar"),
    Ficha("focus", "plan añadir", "✚", "Añadir examen",
          "Apunta un examen o una entrega y Ultron reparte el estudio.",
          (A("asignatura", "Asignatura"), A("fecha", "Fecha (AAAA-MM-DD)"),
           S("--entrega", "Es una entrega, no un examen")), "examen fecha calendario"),
    Ficha("focus", "plan ver", "▥", "Calendario de estudio",
          "Calendario por asignaturas con la cuenta atrás.", claves="calendario"),
    Ficha("focus", "stats", "▮", "Mis estadísticas",
          "Horas por asignatura, rachas y mapa de calor.", claves="estadisticas racha horas"),
    # ── GAMING ─────────────────────────────────────────────────────────────────
    Ficha("gaming", "juegos", "▶", "Biblioteca de juegos",
          "Todos tus juegos (Steam, Lutris, Heroic, Flatpak) en una sola carátula.",
          claves="jugar juegos steam biblioteca", escritorio=True),
    Ficha("gaming", "turbo", "⚡", "Turbo",
          "Perfil de rendimiento máximo: CPU, GameMode y fuera procesos pesados.",
          claves="rendimiento turbo rapido fps", escritorio=True),
    Ficha("gaming", "hud", "◫", "HUD en directo",
          "CPU, GPU, temperaturas y red en un HUD neón a pantalla completa.",
          claves="hud monitor temperatura gpu", escritorio=True),
    Ficha("gaming", "fps", "◷", "Contador de FPS",
          "Activa el contador neón de MangoHud en los juegos.", claves="fps mangohud contador"),
    Ficha("gaming", "visualizador", "♫", "Visualizador de audio",
          "El espectro de la música en neón.", claves="musica audio espectro",
          escritorio=True),
    Ficha("gaming", "clip guardar", "●", "Guardar clip",
          "Guarda los últimos segundos de pantalla en Vídeos.", claves="grabar clip video"),
    Ficha("gaming", "perfil", "★", "Perfil y logros",
          "Tu nivel, XP y logros desbloqueados usando Ultron.", claves="nivel xp logros"),
    Ficha("gaming", "gaming fondo", "▙", "Nueva ciudad neón",
          "Genera otra ciudad cyberpunk para el fondo.", claves="fondo ciudad"),
    # ── PRESENTACIÓN ───────────────────────────────────────────────────────────
    Ficha("presentacion", "diapos", "▶", "Presentar",
          "Diapositivas a pantalla completa desde un Markdown, con notas del orador.",
          (A("archivo", "Presentación .md (vacío = demo)", "archivo", obligatorio=False),),
          "presentar diapositivas", escritorio=True, soltar="archivo"),
    Ficha("presentacion", "ensayo", "☺", "Ensayo con público IA",
          "La IA hace de público: preguntas difíciles y una nota por diapositiva.",
          (A("archivo", "Presentación .md", "archivo"),), "ensayar practicar",
          escritorio=True, soltar="archivo"),
    Ficha("presentacion", "cronometro", "◴", "Cronómetro gigante",
          "Cuenta atrás que se ve desde el fondo del aula.",
          (O("--min", "Minutos", "numero", "10"),), "tiempo cronometro", escritorio=True),
    Ficha("presentacion", "teleprompter", "⇕", "Teleprompter",
          "Tu guion en grande desplazándose solo.",
          (A("archivo", "Guion", "archivo"),), "guion leer", soltar="archivo"),
    # ── FANTASMA ───────────────────────────────────────────────────────────────
    Ficha("fantasma", "rastros", "✗", "Borrar rastros",
          "Recientes, miniaturas, historiales y papelera, fuera.",
          claves="borrar historial rastros limpiar", escritorio=True),
    Ficha("fantasma", "mac", "⇄", "MAC aleatoria",
          "Tu red deja de reconocer tu equipo.", claves="mac anonimo red"),
    Ficha("fantasma", "dns-seguro", "◇", "DNS cifrado",
          "Tus consultas DNS viajan cifradas.", claves="dns cifrar privacidad"),
    Ficha("fantasma", "tor", "◌", "Salir por Tor",
          "Arranca Tor y comprueba que tu tráfico sale por la red Tor.",
          claves="tor anonimo", escritorio=True),
    Ficha("fantasma", "limpiar-meta", "⌫", "Quitar metadatos",
          "Borra GPS, cámara y autor de fotos y PDF antes de compartirlos.",
          (A("destino", "Archivo o carpeta", "archivo"),), "metadatos gps compartir",
          escritorio=True, soltar="destino"),
    Ficha("fantasma", "efimero", "◆", "Shell efímera",
          "Una carpeta en memoria que se destruye al salir.", claves="temporal efimero"),
    Ficha("fantasma", "nota-efimera", "✉", "Nota autodestructiva",
          "Una nota que solo existe en memoria y se borra sola.", claves="nota secreta"),
    Ficha("fantasma", "cofre crear", "▩", "Crear cofre cifrado",
          "Carpeta cifrada con contraseña.", claves="cifrar cofre secreto"),
    Ficha("fantasma", "cofre abrir", "▧", "Abrir cofre", "Monta el cofre en ~/Cofre."),
    # ── COMUNES ────────────────────────────────────────────────────────────────
    Ficha(COMUN, "ia chat", "✦", "Hablar con ULTRON",
          "Chat con la IA, con la personalidad del modo activo.",
          claves="hablar chat ia preguntar conversar", escritorio=True),
    Ficha(COMUN, "haz", "⚙", "Hazlo por mí",
          "Dile qué quieres en tu idioma: propone los comandos y solo los ejecuta si aceptas.",
          (A("peticion", "¿Qué quieres hacer en el equipo?"),),
          "hacer instalar configurar comando ayuda"),
    Ficha(COMUN, "ordenar", "▤", "Ordenar carpeta con IA",
          "La IA decide dónde va cada archivo; se puede deshacer.",
          (A("carpeta", "Carpeta", "carpeta", obligatorio=False, defecto="~/Descargas"),),
          "ordenar organizar carpeta descargas limpiar", escritorio=True, soltar="carpeta"),
    Ficha(COMUN, "buscar", "⌕", "Buscar por contenido",
          "Encuentra archivos por lo que dicen dentro, no por el nombre.",
          (A("consulta", "¿Qué buscas?"),
           A("carpeta", "Dónde (vacío = tu carpeta personal)", "carpeta", obligatorio=False)),
          "buscar encontrar archivo"),
    Ficha(COMUN, "tareas lista", "☑", "Mis tareas", "Tareas de hoy, de la semana y después.",
          claves="tareas pendientes"),
    Ficha(COMUN, "tareas añadir", "✚", "Nueva tarea", "Apunta una tarea.",
          (A("texto", "Tarea"), O("--para", "Para cuándo (hoy, mañana, AAAA-MM-DD)")),
          "tarea recordar apuntar"),
    Ficha(COMUN, "notas nueva", "✐", "Nueva nota", "Apunta una idea rápida.",
          (A("texto", "Nota"),), "nota apuntar idea"),
    Ficha(COMUN, "notas lista", "☷", "Mis notas", "Tus notas, las recientes primero."),
    Ficha(COMUN, "error", "✚", "Arreglar mi último error",
          "La IA lee el último comando que falló y te dice cómo arreglarlo.",
          claves="error fallo arreglar"),
    Ficha(COMUN, "explica-cmd", "?", "Explicar un comando",
          "Trozo a trozo y con su nivel de peligro.", (A("comando", "Comando"),),
          "comando explicar que hace"),
    Ficha(COMUN, "sistema", "▣", "Estado del sistema", "Resumen del equipo con estilo.",
          claves="sistema equipo info"),
    Ficha(COMUN, "musica silenciar", "◁", "Silenciar música",
          "Para la música del modo hasta que vuelvas a entrar.", claves="silencio musica"),
    Ficha(COMUN, "musica reproducir", "♪", "Poner música", "Vuelve a poner la música del modo."),
    Ficha(COMUN, "ia configurar", "⚙", "Configurar la IA",
          "Conecta Ollama, LM Studio o cualquier API compatible.",
          claves="configurar ia modelo api ollama"),
    Ficha(COMUN, "doctor", "✚", "Diagnóstico", "Revisa dependencias, recursos y la IA.",
          (S("--completo", "Revisión completa"),), "diagnostico problema revisar"),
)


def de_modo(id_modo: str | None) -> list[Ficha]:
    return [f for f in FICHAS if f.modo == id_modo]


def comunes() -> list[Ficha]:
    return de_modo(COMUN)


def buscar_comando(comando: str) -> Ficha | None:
    comando = comando.replace("-", " ").strip()
    for f in FICHAS:
        if f.comando.replace("-", " ") == comando or f.id == comando:
            return f
    return None


def _normal(texto: str) -> str:
    sin = unicodedata.normalize("NFKD", texto.lower())
    return "".join(c for c in sin if not unicodedata.combining(c))


def puntuar(ficha: Ficha, consulta: str) -> float:
    """Parecido entre lo que escribe el usuario y una ficha (0 = nada)."""
    palabras = [p for p in _normal(consulta).split() if len(p) > 1]
    if not palabras:
        return 0.0
    titulo = _normal(ficha.titulo)
    resto = _normal(" ".join([ficha.descripcion, ficha.comando, ficha.claves]))
    total = 0.0
    for p in palabras:
        raiz = p[:5] if len(p) > 5 else p
        if raiz in titulo:
            total += 3
        elif raiz in resto:
            total += 1.5
    return total / len(palabras)


def ordenar_por_consulta(fichas: list[Ficha], consulta: str) -> list[Ficha]:
    puntuadas = [(puntuar(f, consulta), i, f) for i, f in enumerate(fichas)]
    return [f for p, _i, f in sorted(puntuadas, key=lambda x: (-x[0], x[1])) if p > 0]
