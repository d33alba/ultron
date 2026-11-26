"""Comandos del modo FOCUS: estudio con PDF, repaso, exámenes, plan, pomodoro, estadísticas."""

from __future__ import annotations

import sys
from collections import defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path

import typer
from rich.align import Align
from rich.live import Live
from rich.markdown import Markdown
from rich.table import Table
from rich.text import Text
from rich.tree import Tree
from typer.core import TyperGroup

from ultron.ia.cliente import preguntar_stream
from ultron.modos.focus import algoritmos, datos, estudio, pomodoro
from ultron.modos.focus.extraer import ErrorExtraccion
from ultron.nucleo.ejecutor import Ejecutor
from ultron.ui import tema
from ultron.ui.teclas import leer_tecla

app = typer.Typer()
ArchivoArg = typer.Argument(..., exists=True, dir_okay=False, help="PDF, txt, md o docx.")


def _t() -> tema.Tema:
    return tema.cargar_tema("focus")


def _fallo(e: Exception) -> None:
    _t().error(str(e))
    raise typer.Exit(1)


def _stream(trozos) -> str:
    c = _t().consola
    partes = []
    for trozo in trozos:
        partes.append(trozo)
        c.print(trozo, end="", markup=False, highlight=False, soft_wrap=True)
    c.print()
    return "".join(partes)


def _mazo(archivo: Path) -> str:
    return archivo.stem


# --- resumen -------------------------------------------------------------------------


@app.command("resumen")
def cmd_resumen(
    archivo: Path = ArchivoArg,
    nivel: str = typer.Option("medio", "--nivel", "-n", help="corto, medio o esquema."),
    guardar: bool = typer.Option(False, "--guardar", help="Guarda <archivo>.resumen.md al lado."),
) -> None:
    """Resume un PDF o unos apuntes (por partes, para que funcione con modelos pequeños)."""
    t = _t()
    try:
        with t.spinner_ctx("leyendo y resumiendo"):
            texto = estudio.resumen(archivo, nivel)
    except ErrorExtraccion as e:
        _fallo(e)
    t.consola.print(t.panel(Markdown(texto), titulo=f"resumen · {archivo.name}"))
    if guardar:
        destino = archivo.with_suffix(".resumen.md")
        destino.write_text(f"# Resumen de {archivo.name}\n\n{texto}\n", encoding="utf-8")
        t.ok(f"guardado en {destino}")


# --- flashcards ------------------------------------------------------------------------

class _GrupoTarjetas(TyperGroup):
    """`ultron flashcards apuntes.pdf` equivale a `ultron flashcards crear apuntes.pdf`."""

    def parse_args(self, ctx, args):  # type: ignore[override]
        if args and args[0] not in self.commands and not args[0].startswith("-"):
            args = ["crear", *args]
        return super().parse_args(ctx, args)


tarjetas_app = typer.Typer(cls=_GrupoTarjetas, no_args_is_help=True,
                           help="Tarjetas de estudio: `ultron flashcards apuntes.pdf`, lista, "
                                "exportar a Anki.")
app.add_typer(tarjetas_app, name="flashcards")


@tarjetas_app.command("crear", hidden=True)
def cmd_flashcards(
    archivo: Path = ArchivoArg,
    n: int = typer.Option(20, "--n", help="Número de tarjetas."),
    anki: Path = typer.Option(None, "--anki", help="Exporta también a este .apkg."),
) -> None:
    """Genera tarjetas de un documento: `ultron flashcards apuntes.pdf --anki mazo.apkg`."""
    t = _t()
    try:
        with t.spinner_ctx("creando tarjetas"):
            tarjetas = estudio.generar_tarjetas(archivo, n)
    except ErrorExtraccion as e:
        _fallo(e)
    mazo = _mazo(archivo)
    estudio.guardar_tarjetas(mazo, tarjetas)
    tabla = t.tabla("#", "Pregunta", "Respuesta", "p.", titulo=f"mazo · {mazo}")
    for i, tj in enumerate(tarjetas, 1):
        tabla.add_row(str(i), tj["pregunta"], tj["respuesta"], str(tj.get("pagina") or ""))
    t.consola.print(tabla)
    t.ok(f"{len(tarjetas)} tarjetas en el mazo «{mazo}». repásalas con: ultron repasar")
    if anki:
        estudio.exportar_anki(mazo, tarjetas, anki)
        t.ok(f"exportado a {anki}")


def _tarjetas_mazo(mazo: str) -> list[dict]:
    with datos.conectar() as con:
        return [dict(f) for f in con.execute(
            "select * from tarjetas where mazo = ? order by id", (mazo,))]


@tarjetas_app.command("lista")
def cmd_lista() -> None:
    """Mazos guardados y cuántas tarjetas tocan hoy."""
    t = _t()
    hoy = date.today().isoformat()
    with datos.conectar() as con:
        filas = con.execute(
            "select mazo, count(*) n, sum(case when proxima is null or proxima <= ? "
            "then 1 else 0 end) hoy from tarjetas group by mazo order by mazo", (hoy,)).fetchall()
    tabla = t.tabla("Mazo", "Tarjetas", "Para hoy")
    for f in filas:
        tabla.add_row(f["mazo"], str(f["n"]), str(f["hoy"]))
    t.consola.print(tabla)


@tarjetas_app.command("borrar")
def cmd_borrar(mazo: str) -> None:
    """Borra un mazo."""
    with datos.conectar() as con:
        n = con.execute("delete from tarjetas where mazo = ?", (mazo,)).rowcount
    _t().ok(f"{n} tarjetas borradas.")


@tarjetas_app.command("exportar")
def cmd_exportar(mazo: str, salida: Path = typer.Argument(None)) -> None:
    """Exporta un mazo a Anki (.apkg)."""
    tarjetas = _tarjetas_mazo(mazo)
    if not tarjetas:
        _fallo(ValueError(f"El mazo «{mazo}» no existe o está vacío."))
    destino = salida or Path(f"{mazo}.apkg")
    estudio.exportar_anki(mazo, tarjetas, destino)
    _t().ok(f"exportado a {destino}")


# --- repasar -------------------------------------------------------------------------------

DEMO_TARJETAS = [
    {"id": 0, "pregunta": "¿Qué es la derivada de una función?",
     "respuesta": "La tasa de cambio instantánea: el límite del cociente incremental.",
     "facilidad": 2.5, "intervalo": 0, "repeticiones": 0},
    {"id": 0, "pregunta": "¿En qué año empezó la Revolución Francesa?",
     "respuesta": "En 1789, con la toma de la Bastilla.", "facilidad": 2.5, "intervalo": 0,
     "repeticiones": 0},
    {"id": 0, "pregunta": "¿Qué orgánulo produce la energía de la célula?",
     "respuesta": "La mitocondria (respiración celular, ATP).", "facilidad": 2.5,
     "intervalo": 0, "repeticiones": 0},
]


def _pendientes(mazo: str | None) -> list[dict]:
    hoy = date.today().isoformat()
    consulta = "select * from tarjetas where (proxima is null or proxima <= ?)"
    args: list = [hoy]
    if mazo:
        consulta += " and mazo = ?"
        args.append(mazo)
    with datos.conectar() as con:
        return [dict(f) for f in con.execute(consulta + " order by proxima, id", args)]


def _guardar_revision(tarjeta: dict, nota: int) -> algoritmos.EstadoTarjeta:
    nuevo = algoritmos.sm2(algoritmos.EstadoTarjeta(
        tarjeta["facilidad"], tarjeta["intervalo"], tarjeta["repeticiones"]), nota)
    if tarjeta.get("id"):
        proxima = (date.today() + timedelta(days=nuevo.intervalo)).isoformat()
        with datos.conectar() as con:
            con.execute("update tarjetas set facilidad=?, intervalo=?, repeticiones=?, proxima=? "
                        "where id=?", (nuevo.facilidad, nuevo.intervalo, nuevo.repeticiones,
                                       proxima, tarjeta["id"]))
            con.execute("insert into revisiones(tarjeta, nota, fecha) values (?, ?, ?)",
                        (tarjeta["id"], nota, datos.ahora()))
    return nuevo


@app.command("repasar")
def cmd_repasar(
    mazo: str = typer.Argument(None, help="Mazo (vacío: todos)."),
    demo: bool = typer.Option(False, "--demo", help="Tarjetas de ejemplo, sin guardar nada."),
) -> None:
    """Repaso con repetición espaciada (SM-2): espacio muestra la respuesta, 1-4 puntúa."""
    t = _t()
    c = t.consola
    tarjetas = [dict(x) for x in DEMO_TARJETAS] if demo else _pendientes(mazo)
    if not tarjetas:
        t.ok("nada que repasar hoy. vuelve mañana.")
        return
    interactivo = sys.stdin.isatty() and sys.stdout.isatty()
    notas: list[int] = []
    for i, tj in enumerate(tarjetas, 1):
        c.print()
        c.print(t.barra(i / len(tarjetas), 30), f"[apagado] {i}/{len(tarjetas)}[/]")
        c.print(t.panel(Align.center(Text(tj["pregunta"], style="bold texto")), titulo="pregunta"))
        if interactivo:
            c.print("[apagado]espacio: ver respuesta · q: salir[/]")
            if leer_tecla() in ("q", "Q"):
                break
        c.print(t.panel(Align.center(Text(tj["respuesta"], style="acento")), titulo="respuesta"))
        if interactivo:
            c.print("[apagado]1 otra vez · 2 difícil · 3 bien · 4 fácil[/]")
            tecla = ""
            while tecla not in ("1", "2", "3", "4", "q"):
                tecla = leer_tecla()
            if tecla == "q":
                break
            nota = int(tecla)
        else:
            nota = 3
        nuevo = _guardar_revision(tj, nota) if not demo else algoritmos.sm2(
            algoritmos.EstadoTarjeta(), nota)
        notas.append(nota)
        c.print(f"[apagado]próximo repaso en {nuevo.intervalo} día(s)[/]")
    if notas:
        bien = sum(n >= 3 for n in notas)
        c.print()
        t.ok(f"sesión hecha: {len(notas)} tarjetas · {round(100 * bien / len(notas))}% bien.")


# --- examen ----------------------------------------------------------------------------------


@app.command("examen")
def cmd_examen(
    archivo: Path = ArchivoArg,
    n: int = typer.Option(10, "--n", help="Número de preguntas."),
    tipo: str = typer.Option("mixto", "--tipo", help="test, corta o mixto."),
) -> None:
    """Examen generado a partir del documento, con nota y corrección."""
    t = _t()
    c = t.consola
    try:
        with t.spinner_ctx("preparando el examen"):
            preguntas = estudio.generar_examen(archivo, n, tipo)
    except ErrorExtraccion as e:
        _fallo(e)
    if not preguntas:
        _fallo(ValueError("La IA no ha generado preguntas válidas. prueba otra vez."))
    puntos, fallidas = 0.0, []
    for i, p in enumerate(preguntas, 1):
        c.print()
        c.print(t.panel(Text(p["pregunta"], style="bold texto"),
                        titulo=f"pregunta {i}/{len(preguntas)}"))
        if p["tipo"] == "test":
            for k, opcion in enumerate(p["opciones"]):
                c.print(f"  [acento]{'abcd'[k]})[/] {opcion}")
            elegida = typer.prompt("respuesta", default="a").strip().lower()[:1]
            acierto = "abcd".find(elegida) == p["correcta"]
            nota = 10.0 if acierto else 0.0
            correcta = p["opciones"][p["correcta"]]
            comentario = "correcto." if acierto else f"la correcta era: {correcta}"
            modelo = correcta
        else:
            respuesta = typer.prompt("respuesta")
            with t.spinner_ctx("corrigiendo"):
                r = estudio.corregir_corta(p["pregunta"], p["respuesta"], respuesta)
            nota, comentario, modelo = r["nota"], r["comentario"], p["respuesta"]
        estilo = "ok" if nota >= 5 else "error"
        pagina = f" [apagado](p. {p['pagina']})[/]" if p.get("pagina") else ""
        c.print(f"  [{estilo}]{nota:.1f}/10[/] {comentario}{pagina}")
        puntos += nota
        if nota < 5:
            fallidas.append({"pregunta": p["pregunta"], "respuesta": modelo,
                             "pagina": p.get("pagina")})
    final = puntos / len(preguntas)
    c.print()
    c.print(t.panel(Align.center(Text(f"{final:.1f} / 10", style="bold acento")),
                    titulo="nota final"))
    if fallidas:
        estudio.guardar_tarjetas(f"{_mazo(archivo)} (fallos)", fallidas)
        t.info(f"{len(fallidas)} preguntas falladas pasan a tarjetas: "
               f"ultron repasar \"{_mazo(archivo)} (fallos)\"")


# --- pregunta / esquema / explica ------------------------------------------------------------


@app.command("pregunta")
def cmd_pregunta(archivo: Path = ArchivoArg, duda: str = typer.Argument(...)) -> None:
    """Pregunta algo sobre el documento; la respuesta cita la página."""
    try:
        prompt, paginas = estudio.contexto_pregunta(archivo, duda)
    except ErrorExtraccion as e:
        _fallo(e)
    t = _t()
    t.consola.print(f"[apagado]buscando en las páginas {', '.join(map(str, paginas))}…[/]")
    _stream(preguntar_stream(prompt))


def _arbol_rich(nodo: dict, t: tema.Tema) -> Tree:
    raiz = Tree(Text(nodo["concepto"], style="bold acento"), guide_style="apagado")

    def añadir(rama: Tree, hijos: list[dict], nivel: int) -> None:
        for h in hijos:
            sub = rama.add(Text(h["concepto"], style="primario" if nivel == 1 else "texto"))
            añadir(sub, h["hijos"], nivel + 1)

    añadir(raiz, nodo["hijos"], 1)
    return raiz


@app.command("esquema")
def cmd_esquema(
    archivo: Path = ArchivoArg,
    png: Path = typer.Option(None, "--png", help="Guarda el mapa como imagen."),
    mermaid: bool = typer.Option(False, "--mermaid", help="Saca el mapa en Mermaid."),
) -> None:
    """Mapa conceptual del documento (árbol en la terminal, PNG o Mermaid)."""
    t = _t()
    try:
        with t.spinner_ctx("dibujando el mapa"):
            arbol = estudio.generar_esquema(archivo)
    except ErrorExtraccion as e:
        _fallo(e)
    if mermaid:
        t.consola.print(estudio.a_mermaid(arbol), markup=False)
        return
    t.consola.print(t.panel(_arbol_rich(arbol, t), titulo=f"esquema · {archivo.name}"))
    if png:
        estudio.a_png(arbol, png, t.paleta)
        t.ok(f"imagen guardada en {png}")


@app.command("explica")
def cmd_explica(
    concepto: str = typer.Argument(...),
    nivel: str = typer.Option("todos", "--nivel", help="1 (simple), 2, 3 (experto) o todos."),
) -> None:
    """Explicación a tres niveles con ejemplo y pregunta de comprobación."""
    _stream(preguntar_stream(estudio.prompt_explica(concepto, nivel)))


# --- plan ---------------------------------------------------------------------------------------

plan_app = typer.Typer(help="Plan de estudio día a día hasta tus exámenes y entregas.",
                       invoke_without_command=True)
app.add_typer(plan_app, name="plan")


def _eventos() -> list[tuple[int, algoritmos.Evento]]:
    with datos.conectar() as con:
        filas = con.execute("select * from examenes order by fecha").fetchall()
    return [(f["id"], algoritmos.Evento(
        f["asignatura"], date.fromisoformat(f["fecha"]),
        [x.strip() for x in (f["temas"] or "").split(",") if x.strip()], f["horas"], f["tipo"]))
        for f in filas]


@plan_app.callback()
def cmd_plan(ctx: typer.Context) -> None:
    """Sin subcomando: muestra el plan de hoy."""
    if ctx.invoked_subcommand is None:
        cmd_hoy()


@plan_app.command("añadir")
def cmd_anadir(
    asignatura: str,
    fecha: str = typer.Argument(..., help="AAAA-MM-DD"),
    temas: str = typer.Option("", "--temas", help="Temas separados por comas."),
    horas: float = typer.Option(6.0, "--horas", help="Horas totales de estudio."),
    entrega: bool = typer.Option(False, "--entrega", help="Es una entrega, no un examen."),
) -> None:
    """Añade un examen o una entrega."""
    try:
        date.fromisoformat(fecha)
    except ValueError:
        _fallo(ValueError("La fecha va así: 2026-12-10"))
    with datos.conectar() as con:
        con.execute("insert into examenes(asignatura, fecha, temas, horas, tipo) "
                    "values (?, ?, ?, ?, ?)",
                    (asignatura, fecha, temas, horas, "entrega" if entrega else "examen"))
    _t().ok(f"{asignatura} el {fecha} añadido. mira el plan con: ultron plan ver")


@plan_app.command("quitar")
def cmd_quitar(id_evento: int) -> None:
    """Quita un examen o entrega por su número (ver: ultron plan lista)."""
    with datos.conectar() as con:
        con.execute("delete from examenes where id = ?", (id_evento,))
    _t().ok("quitado.")


@plan_app.command("lista")
def cmd_lista_plan() -> None:
    """Exámenes y entregas, con la cuenta atrás."""
    t = _t()
    tabla = t.tabla("#", "Asignatura", "Tipo", "Fecha", "Faltan", "Temas")
    for i, ev in _eventos():
        dias = (ev.fecha - date.today()).days
        estilo = "error" if dias <= 2 else "aviso" if dias <= 7 else "texto"
        tabla.add_row(str(i), ev.asignatura, ev.tipo, ev.fecha.isoformat(),
                      f"[{estilo}]{dias} d[/]", ", ".join(ev.temas))
    t.consola.print(tabla)


@plan_app.command("hoy")
def cmd_hoy() -> None:
    """Lo que toca estudiar hoy."""
    t = _t()
    plan = algoritmos.generar_plan([e for _, e in _eventos()], date.today())
    bloques = plan.get(date.today(), [])
    if not bloques:
        t.info("hoy no hay nada planificado. añade un examen: ultron plan añadir …")
        return
    for b in bloques:
        t.consola.print(f"  [acento]{t.glifo('vineta')}[/] [bold]{b.asignatura}[/] "
                        f"[apagado]{b.tipo} · {b.horas:g} h[/]  {b.tema}")


COLORES = ["#8FBC8F", "#D9A441", "#7FA7C9", "#C97064", "#B39DDB", "#80CBC4"]


@plan_app.command("ver")
def cmd_ver(dias: int = typer.Option(14, "--dias", help="Días a mostrar.")) -> None:
    """Calendario de estudio con colores por asignatura."""
    t = _t()
    eventos = [e for _, e in _eventos()]
    plan = algoritmos.generar_plan(eventos, date.today())
    colores = {a: COLORES[i % len(COLORES)]
               for i, a in enumerate(dict.fromkeys(e.asignatura for e in eventos))}
    tabla = t.tabla("Día", "Plan", "Horas")
    for d in range(dias):
        dia = date.today() + timedelta(days=d)
        bloques = plan.get(dia, [])
        examen = [e for e in eventos if e.fecha == dia]
        texto = Text()
        for e in examen:
            texto.append(f"★ {e.tipo.upper()} {e.asignatura}  ",
                         style=f"bold {colores[e.asignatura]}")
        for b in bloques:
            texto.append(f"■ {b.asignatura} ({b.tipo}) ", style=colores[b.asignatura])
        tabla.add_row(dia.strftime("%a %d/%m"), texto,
                      f"{sum(b.horas for b in bloques):g}" if bloques else "")
    t.consola.print(tabla)


@plan_app.command("proximo", hidden=True)
def cmd_proximo() -> None:
    """Siguiente examen en una línea (lo usa el widget de Conky)."""
    futuros = [e for _, e in _eventos() if e.fecha >= date.today()]
    if futuros:
        e = futuros[0]
        sys.stdout.write(f"{e.asignatura} en {(e.fecha - date.today()).days} días")


# --- pomodoro ---------------------------------------------------------------------------------

pomo_app = typer.Typer(help="Pomodoro con bloqueo de webs.", invoke_without_command=True)
app.add_typer(pomo_app, name="pomodoro")


def _vista_pomodoro(t: tema.Tema, fase: pomodoro.Fase, asignatura: str | None) -> Table:
    m, s = divmod(int(fase.restante), 60)
    fases = "○◔◑◕●"
    progreso = 1 - fase.restante / fase.total if fase.total else 1
    caja = Table.grid()
    caja.add_column(justify="center")
    titulo = f"sesión {fase.ciclo} · {'trabajo' if fase.nombre == 'trabajo' else 'descanso'}"
    if asignatura:
        titulo += f" · {asignatura}"
    caja.add_row(Text(titulo, style="apagado"))
    caja.add_row("")
    estilo = "acento" if fase.nombre == "trabajo" else "aviso"
    for linea in pomodoro.digitos_grandes(f"{m:02d}:{s:02d}"):
        caja.add_row(Text(linea, style=estilo))
    caja.add_row("")
    caja.add_row(Text(f"{fases[min(4, int(progreso * 4.999))]}  ", style=estilo) +
                 t.barra(progreso, 30, estilo))
    return caja


@pomo_app.callback()
def cmd_pomodoro(
    ctx: typer.Context,
    minutos: float = typer.Option(25, "--min", help="Minutos de trabajo."),
    descanso: float = typer.Option(5, "--descanso", help="Minutos de descanso."),
    ciclos: int = typer.Option(4, "--ciclos", help="Número de ciclos."),
    asignatura: str = typer.Option(None, "--asignatura", "-a", help="Para las estadísticas."),
    sin_bloqueo: bool = typer.Option(False, "--sin-bloqueo", help="No bloquees webs."),
) -> None:
    """Temporizador grande; bloquea webs de distracción mientras trabajas."""
    if ctx.invoked_subcommand is not None:
        return
    t = _t()
    ej = Ejecutor(consola=t.consola)
    inicio = datetime.now()
    if not sin_bloqueo:
        t.info(f"bloqueando {len(pomodoro.webs())} webs durante el trabajo (pide sudo).")
    from ultron.capas.sonido import reproductor_efecto
    from ultron.nucleo import registro

    campana = registro.obtener("focus").recurso("tema/sonidos/campana.wav")
    prog = reproductor_efecto(ej)

    def sonar(_fase: pomodoro.Fase) -> None:
        if campana.exists() and prog:
            ej.run([*prog, str(campana)], check=False, fondo=True)

    trabajados = 0.0
    with Live(console=t.consola, refresh_per_second=4, transient=True) as live:
        try:
            trabajados = pomodoro.ejecutar(
                minutos=minutos, descanso=descanso, ciclos=ciclos, ej=ej,
                al_tick=lambda f: live.update(Align.center(_vista_pomodoro(t, f, asignatura))),
                al_terminar_fase=sonar, bloquear=not sin_bloqueo)
        except KeyboardInterrupt:
            trabajados = (datetime.now() - inicio).total_seconds() / 60
    if trabajados > 0.5:
        with datos.conectar() as con:
            con.execute("insert into sesiones(asignatura, inicio, minutos) values (?, ?, ?)",
                        (asignatura or "general", inicio.isoformat(timespec="seconds"),
                         round(trabajados, 1)))
    t.ok(f"{trabajados:.0f} minutos de concentración. webs desbloqueadas.")


@pomo_app.command("webs")
def cmd_webs(
    accion: str = typer.Argument("lista", help="lista, añadir o quitar."),
    dominio: str = typer.Argument(None),
) -> None:
    """Webs que se bloquean durante el pomodoro."""
    t = _t()
    lista = pomodoro.webs()
    if accion == "añadir" and dominio:
        pomodoro.guardar_webs(lista + [dominio])
        t.ok(f"{dominio} se bloqueará.")
    elif accion == "quitar" and dominio:
        pomodoro.guardar_webs([w for w in lista if w != dominio])
        t.ok(f"{dominio} ya no se bloquea.")
    else:
        for w in lista:
            t.consola.print(f"  [apagado]·[/] {w}")


# --- estadísticas -------------------------------------------------------------------------------

NIVELES_COLOR = ["#2A2B2E", "#3D5C3D", "#5A8A5A", "#7DB37D", "#A8E6A8"]


def datos_demo(hoy: date) -> tuple[dict[date, float], dict[str, float], int, int]:
    import random

    rng = random.Random(7)
    minutos = {}
    for d in range(140):
        dia = hoy - timedelta(days=d)
        if rng.random() < 0.72 or d < 9:
            minutos[dia] = rng.choice([20, 45, 60, 90, 150])
    por_asignatura = {"Matemáticas": 31.5, "Historia": 18.0, "Biología": 12.5, "Inglés": 7.0}
    return minutos, por_asignatura, 412, 87


def mapa_texto(minutos: dict[date, float], hoy: date, semanas: int = 20) -> Text:
    filas = algoritmos.mapa_calor(minutos, hoy, semanas)
    nombres = ["lun", "   ", "mié", "   ", "vie", "   ", "dom"]
    texto = Text()
    for i, fila in enumerate(filas):
        texto.append(f"{nombres[i]} ", style="apagado")
        for nivel in fila:
            texto.append("  " if nivel < 0 else "■ ", style=NIVELES_COLOR[max(0, nivel)])
        texto.append("\n")
    texto.append("     menos ", style="apagado")
    for color in NIVELES_COLOR:
        texto.append("■ ", style=color)
    texto.append("más", style="apagado")
    return texto


@app.command("stats")
def cmd_stats(demo: bool = typer.Option(False, "--demo", help="Datos de ejemplo.")) -> None:
    """Horas por asignatura, rachas, tarjetas y mapa de calor de las últimas 20 semanas."""
    t = _t()
    c = t.consola
    hoy = date.today()
    if demo:
        minutos, por_asig, repasadas, precision = datos_demo(hoy)
    else:
        minutos = defaultdict(float)
        por_asig: dict[str, float] = defaultdict(float)
        with datos.conectar() as con:
            for f in con.execute("select asignatura, inicio, minutos from sesiones"):
                minutos[date.fromisoformat(f["inicio"][:10])] += f["minutos"]
                por_asig[f["asignatura"]] += f["minutos"] / 60
            revs = con.execute("select nota from revisiones").fetchall()
        repasadas = len(revs)
        precision = round(100 * sum(r["nota"] >= 3 for r in revs) / repasadas) if revs else 0
    actual, maxima = algoritmos.rachas({d for d, m in minutos.items() if m > 0}, hoy)
    total = sum(por_asig.values()) if por_asig else 0
    tabla = t.tabla("Asignatura", "Horas", "")
    for asig, horas in sorted(por_asig.items(), key=lambda x: -x[1]):
        tabla.add_row(asig, f"{horas:.1f}", t.barra(horas / max(por_asig.values()), 24))
    c.print(t.panel(mapa_texto(minutos, hoy), titulo="últimas 20 semanas"))
    if por_asig:
        c.print(tabla)
    c.print(f"  [acento]racha[/] {actual} días [apagado](máxima {maxima})[/]   "
            f"[acento]total[/] {total:.1f} h   [acento]tarjetas[/] {repasadas} "
            f"[apagado]({precision}% bien)[/]")
