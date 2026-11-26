"""Telemetría local y pantalla del jugador."""

import time
from collections import deque
from pathlib import Path

import psutil
from rich import box
from rich.panel import Panel
from rich.text import Text
from textual.app import App, ComposeResult
from textual.containers import VerticalScroll
from textual.widgets import Button, DataTable, Footer, Label, Static

from ultron.nucleo import xp
from ultron.ui.banner import aplicar_degradado


def gpu(ej) -> float | None:
    if ej.existe("nvidia-smi"):
        resultado = ej.leer(["nvidia-smi", "--query-gpu=utilization.gpu",
                             "--format=csv,noheader,nounits"], timeout=2)
        if resultado.ok:
            try:
                return max(float(valor) for valor in resultado.salida.splitlines())
            except ValueError:
                pass
    for archivo in Path("/sys/class/drm").glob("card*/device/gpu_busy_percent"):
        try:
            return float(archivo.read_text())
        except (OSError, ValueError):
            continue
    return None


def procesos() -> list[tuple[int, str, int]]:
    filas = [(p.pid, p.info["name"] or "?", p.info["memory_info"].rss)
             for p in psutil.process_iter(["name", "memory_info"]) if p.info["memory_info"]]
    return sorted(filas, key=lambda p: p[2], reverse=True)[:5]


def barra(porcentaje: float, ascii_: bool = False) -> str:
    lleno = min(10, max(0, round(porcentaje / 10)))
    return ("#" if ascii_ else "▰") * lleno + ("-" if ascii_ else "▱") * (10 - lleno)


class Medidor:
    def __init__(self, ej, demo: bool = False):
        self.ej = ej
        self.demo = demo
        self.anterior = None
        self.red = deque(maxlen=20)

    def cuadro(self, ascii_: bool = False) -> Panel:
        if self.demo:
            cpu, ram, swap, video, temp, disco = [68, 44, 55, 71], 52, 12, 44, 61, 38
            filas = [(123, "Juego de demostración", 650 * 1024**2)]
            subida, bajada = 12.0, 64.0
        else:
            cpu = psutil.cpu_percent(percpu=True)
            ram, swap, video = psutil.virtual_memory().percent, psutil.swap_memory().percent, gpu(
                self.ej
            )
            sensores = getattr(psutil, "sensors_temperatures", lambda: {})()
            temp = max((s.current for grupo in sensores.values() for s in grupo), default=None)
            disco = psutil.disk_usage(Path.home()).percent
            filas = procesos()
            red = psutil.net_io_counters()
            ahora = time.monotonic()
            subida, bajada = 0.0, 0.0
            if red and self.anterior:
                reloj, enviado, recibido = self.anterior
                delta = max(0.001, ahora - reloj)
                subida = max(0, red.bytes_sent - enviado) / delta / 1024
                bajada = max(0, red.bytes_recv - recibido) / delta / 1024
            if red:
                self.anterior = ahora, red.bytes_sent, red.bytes_recv
        self.red.append((subida, bajada))
        puntos = " .:-=+*#" if ascii_ else "▁▂▃▄▅▆▇█"
        superior = max((max(par) for par in self.red), default=1) or 1
        grafico = ["".join(puntos[int(7 * par[i] / superior)] for par in self.red)
                   for i in (0, 1)]
        total = 820 if self.demo else xp.leer()["xp"]
        nivel = xp.nivel(total)
        minimo, maximo = 50 * nivel**2, 50 * (nivel + 1)**2
        texto = Text()
        indicadores = [
            ("HP  CPU", sum(cpu) / max(1, len(cpu)), "#39FF14"),
            ("MP  RAM", ram, "#00F0FF"), ("Intercambio", swap, "#8A2BE2"),
            ("GPU", video, "#FF00E6"), ("Disco", disco, "#00F0FF"),
        ]
        for nombre, valor, color in indicadores:
            texto.append(f"{nombre:<13}", color)
            texto.append("N/D\n" if valor is None else f"{barra(valor, ascii_)} {valor:5.1f}%\n",
                         color)
        texto.append(f"XP · NVL {nivel:<3} {barra(100*(total-minimo)/(maximo-minimo), ascii_)}"
                     f" {total}/{maximo}\n", "#FFE600")
        texto.append("Núcleos  " + " ".join(f"{i}:{v:.0f}%" for i, v in enumerate(cpu, 1)) + "\n")
        texto.append(f"Temperatura  {temp:.0f} °C\n" if temp is not None else "Temperatura  N/D\n")
        texto.append(f"Red ↑ {subida:.1f} {grafico[0]}  ↓ {bajada:.1f} {grafico[1]} KiB/s\n")
        texto.append("\nProcesos por RAM\n", "#8A2BE2")
        for pid, nombre, memoria in filas:
            texto.append(f"{pid:>6}  {nombre}  {memoria / 1024**2:.0f} MiB\n")
        titulo = Text("HUD DEL SISTEMA")
        aplicar_degradado(titulo, ["#FF00E6", "#8A2BE2", "#00F0FF"], len(titulo))
        return Panel(texto, title=titulo, border_style="#FF00E6", box=box.HEAVY)


class PantallaHUD(App):
    BINDINGS = [("q", "quit", "Salir")]

    def __init__(self, medidor: Medidor):
        super().__init__()
        self.medidor = medidor

    def compose(self) -> ComposeResult:
        yield VerticalScroll(Static(self.medidor.cuadro()))

    def on_mount(self) -> None:
        self.set_interval(1, self.actualizar)

    def actualizar(self) -> None:
        self.query_one(Static).update(self.medidor.cuadro())



class PantallaProcesos(App):
    """Selecciona un proceso de la lista y confirma antes de terminarlo."""

    BINDINGS = [("q", "quit", "Salir")]

    def __init__(self, simular: bool):
        super().__init__()
        self.simular = simular
        self.pendiente = None
        self.filas = []

    def compose(self) -> ComposeResult:
        yield DataTable(cursor_type="row")
        yield Button("Terminar proceso", id="terminar", variant="error")
        yield Label("Selecciona una fila.", id="aviso")
        yield Footer()

    def on_mount(self) -> None:
        tabla = self.query_one(DataTable)
        tabla.add_columns("PID", "Proceso", "RAM")
        self._cargar()

    def _cargar(self) -> None:
        tabla = self.query_one(DataTable)
        tabla.clear()
        self.filas = procesos()
        for pid, nombre, memoria in self.filas:
            tabla.add_row(str(pid), Text(nombre), f"{memoria / 1024**2:.0f} MiB")
        tabla.focus()

    def on_button_pressed(self, evento: Button.Pressed) -> None:
        tabla = self.query_one(DataTable)
        aviso = self.query_one("#aviso", Label)
        if not self.filas:
            return
        pid = self.filas[tabla.cursor_row][0]
        if self.simular or pid == psutil.Process().pid:
            aviso.update("La simulación o el propio Ultron no se pueden terminar desde aquí.")
            return
        try:
            proceso = psutil.Process(pid)
            identidad = (pid, proceso.create_time())
            if self.pendiente != identidad:
                self.pendiente = identidad
                aviso.update(f"Confirma que quieres terminar el proceso {pid}.")
                evento.button.label = "Confirmar"
                return
            proceso.terminate()
            aviso.update(f"Se solicitó terminar el proceso {pid}.")
        except psutil.Error:
            aviso.update(f"No se pudo terminar el proceso {pid}.")
        self.pendiente = None
        evento.button.label = "Terminar proceso"
        self._cargar()
