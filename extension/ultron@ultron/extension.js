// Ultron: indicador del panel superior (GNOME 45+).
// Lee ~/.local/state/ultron/panel.json, que escribe el CLI.

import GLib from 'gi://GLib';
import Gio from 'gi://Gio';
import GObject from 'gi://GObject';
import St from 'gi://St';
import Clutter from 'gi://Clutter';

import {Extension} from 'resource:///org/gnome/shell/extensions/extension.js';
import * as Main from 'resource:///org/gnome/shell/ui/main.js';
import * as PanelMenu from 'resource:///org/gnome/shell/ui/panelMenu.js';
import * as PopupMenu from 'resource:///org/gnome/shell/ui/popupMenu.js';

const FASES = ['○', '◔', '◑', '◕', '●'];

function rutaPanel() {
    const xdg = GLib.getenv('XDG_STATE_HOME') || GLib.build_filenamev([GLib.get_home_dir(), '.local', 'state']);
    return GLib.build_filenamev([xdg, 'ultron', 'panel.json']);
}

function leerPanel() {
    try {
        const [ok, datos] = GLib.file_get_contents(rutaPanel());
        if (!ok)
            return {};
        return JSON.parse(new TextDecoder().decode(datos));
    } catch (e) {
        return {};
    }
}

function lanzar(argv) {
    try {
        GLib.spawn_async(null, argv, null, GLib.SpawnFlags.SEARCH_PATH, null);
    } catch (e) {
        logError(e, 'Ultron: no se pudo lanzar ' + argv.join(' '));
    }
}

function comando(panel) {
    return panel.comando || 'ultron';
}

function abrirTerminal(argv, completa = false) {
    for (const terminal of ['gnome-terminal', 'ptyxis', 'kgx', 'x-terminal-emulator']) {
        if (GLib.find_program_in_path(terminal)) {
            const sep = terminal === 'kgx' ? '-e' : '--';
            const extra = completa && terminal === 'gnome-terminal' ? ['--full-screen'] : [];
            lanzar([terminal, ...extra, sep, ...argv]);
            return;
        }
    }
}

// Rótulo a pantalla completa al cambiar de modo: el «momento JARVIS» al cerrar la terminal.
function mostrarRotulo(panel) {
    const monitor = Main.layoutManager.primaryMonitor;
    if (!monitor)
        return;
    const acento = panel.acento || '#00D7FF';
    const caja = new St.BoxLayout({vertical: true, x_align: Clutter.ActorAlign.CENTER,
        y_align: Clutter.ActorAlign.CENTER});
    const textos = panel.modo
        ? [[panel.glifo || '◆', `font-size: 110px; color: ${acento};`],
            [`MODO ${panel.nombre}`, 'font-size: 76px; font-weight: 800; color: #FFFFFF;'],
            [panel.lema ? `«${panel.lema}»` : '', `font-size: 30px; color: ${acento}; font-style: italic;`],
            ['Funciones en el dock, el escritorio y el menú ◆  ·  Super+U abre el NEXUS',
                'font-size: 20px; color: rgba(255,255,255,0.7); padding-top: 28px;']]
        : [['◆', 'font-size: 90px; color: #FFFFFF;'],
            ['UBUNTU RESTAURADO', 'font-size: 64px; font-weight: 800; color: #FFFFFF;'],
            ['Todo ha vuelto exactamente como estaba', 'font-size: 24px; color: rgba(255,255,255,0.7);']];
    for (const [texto, estilo] of textos) {
        if (!texto)
            continue;
        caja.add_child(new St.Label({text: texto, style: estilo, x_align: Clutter.ActorAlign.CENTER}));
    }
    const fondo = new St.Bin({child: caja, reactive: false, x: monitor.x, y: monitor.y,
        width: monitor.width, height: monitor.height,
        style: 'background-color: rgba(0, 0, 0, 0.78);'});
    Main.layoutManager.uiGroup.add_child(fondo);
    fondo.opacity = 0;
    caja.set_pivot_point(0.5, 0.5);
    caja.scale_x = 1.25;
    caja.scale_y = 1.25;
    caja.ease({scale_x: 1, scale_y: 1, duration: 900, mode: Clutter.AnimationMode.EASE_OUT_EXPO});
    fondo.ease({
        opacity: 255, duration: 450, mode: Clutter.AnimationMode.EASE_OUT_QUAD,
        onComplete: () => {
            GLib.timeout_add(GLib.PRIORITY_DEFAULT, 2600, () => {
                fondo.ease({opacity: 0, duration: 800, mode: Clutter.AnimationMode.EASE_IN_QUAD,
                    onComplete: () => fondo.destroy()});
                return GLib.SOURCE_REMOVE;
            });
        },
    });
}

const Indicador = GObject.registerClass(
class UltronIndicador extends PanelMenu.Button {
    _init() {
        super._init(0.5, 'Ultron');
        this._caja = new St.BoxLayout({style_class: 'ultron-caja'});
        this._glifo = new St.Label({text: '◆', y_align: Clutter.ActorAlign.CENTER,
            style_class: 'ultron-glifo'});
        this._texto = new St.Label({text: 'ULTRON', y_align: Clutter.ActorAlign.CENTER,
            style_class: 'ultron-texto'});
        this._extra = new St.Label({text: '', y_align: Clutter.ActorAlign.CENTER,
            style_class: 'ultron-extra'});
        this._caja.add_child(this._glifo);
        this._caja.add_child(this._texto);
        this._caja.add_child(this._extra);
        this.add_child(this._caja);
        this._firmaMenu = '';
    }

    actualizar(panel) {
        const acento = panel.acento || '#00D7FF';
        this._glifo.text = panel.glifo || '◆';
        this._glifo.style = `color: ${acento};`;
        this._texto.text = panel.nombre || 'ULTRON';
        const partes = [];
        const pomo = panel.pomodoro;
        if (pomo && pomo.fin) {
            const restante = Math.max(0, pomo.fin - Date.now() / 1000);
            if (restante > 0) {
                const total = pomo.total || 1500;
                const fase = FASES[Math.min(4, Math.floor((1 - restante / total) * 4.999))];
                const m = String(Math.floor(restante / 60)).padStart(2, '0');
                const s = String(Math.floor(restante % 60)).padStart(2, '0');
                partes.push(`${fase} ${m}:${s}`);
            }
        }
        if (panel.modo === 'gaming' && panel.nivel !== undefined && panel.nivel !== null)
            partes.push(`LVL ${panel.nivel}`);
        this._extra.text = partes.length ? '  ' + partes.join(' · ') : '';
        this._reconstruirMenu(panel);
    }

    _reconstruirMenu(panel) {
        const modos = panel.modos || [];
        const firma = JSON.stringify([panel.modo, modos, panel.funciones || []]);
        if (firma === this._firmaMenu)
            return;
        this._firmaMenu = firma;
        this.menu.removeAll();
        const cmd = comando(panel);
        const nexus = new PopupMenu.PopupMenuItem('◆  Abrir el NEXUS (Super+U)');
        nexus.connect('activate', () => abrirTerminal([cmd, 'nexus'], true));
        this.menu.addMenuItem(nexus);
        const funciones = panel.funciones || [];
        if (panel.modo && funciones.length) {
            const sub = new PopupMenu.PopupSubMenuMenuItem(`Funciones de ${panel.nombre}`);
            for (const f of funciones) {
                const item = new PopupMenu.PopupMenuItem(`${f.icono}   ${f.titulo}`);
                item.connect('activate', () => abrirTerminal([cmd, 'lanzar', f.id]));
                sub.menu.addMenuItem(item);
            }
            this.menu.addMenuItem(sub);
            sub.setSubmenuShown?.(true);
        }
        this.menu.addMenuItem(new PopupMenu.PopupSeparatorMenuItem());
        const titulo = new PopupMenu.PopupMenuItem('Cambiar de modo', {reactive: false});
        this.menu.addMenuItem(titulo);
        for (const modo of modos) {
            const item = new PopupMenu.PopupMenuItem(modo.nombre);
            if (modo.id === panel.modo)
                item.setOrnament(PopupMenu.Ornament.CHECK);
            item.connect('activate', () => lanzar([cmd, 'entrar', modo.id, '--si', '--sin-animaciones']));
            this.menu.addMenuItem(item);
        }
        this.menu.addMenuItem(new PopupMenu.PopupSeparatorMenuItem());
        if (panel.modo) {
            const salir = new PopupMenu.PopupMenuItem('Salir del modo (restaurar todo)');
            salir.connect('activate', () => lanzar([cmd, 'salir']));
            this.menu.addMenuItem(salir);
        }
    }
});

const Bocina = GObject.registerClass(
class UltronBocina extends PanelMenu.Button {
    _init() {
        super._init(0.5, 'Ultron música', true);
        this.add_child(new St.Icon({icon_name: 'audio-volume-high-symbolic',
            style_class: 'system-status-icon ultron-bocina'}));
        this._comando = 'ultron';
        this.connect('button-press-event', () => {
            lanzar([this._comando, 'musica', 'silenciar']);
            this.hide();
            return Clutter.EVENT_STOP;
        });
    }

    actualizar(panel) {
        this._comando = comando(panel);
        this.visible = Boolean(panel.musica_sonando && !panel.musica_silenciada);
    }
});

export default class UltronExtension extends Extension {
    enable() {
        this._indicador = new Indicador();
        this._bocina = new Bocina();
        Main.panel.addToStatusArea(`${this.uuid}-indicador`, this._indicador, 0, 'right');
        Main.panel.addToStatusArea(`${this.uuid}-bocina`, this._bocina, 0, 'right');
        this._refrescar();
        const archivo = Gio.File.new_for_path(rutaPanel());
        try {
            this._monitor = archivo.monitor_file(Gio.FileMonitorFlags.NONE, null);
            this._idMonitor = this._monitor.connect('changed', () => this._refrescar());
        } catch (e) {
            this._monitor = null;
        }
        this._idTiempo = GLib.timeout_add_seconds(GLib.PRIORITY_DEFAULT, 1, () => {
            this._refrescar();
            return GLib.SOURCE_CONTINUE;
        });
    }

    _refrescar() {
        const panel = leerPanel();
        if (panel.entrada !== undefined && panel.entrada !== this._entrada) {
            const reciente = Date.now() / 1000 - panel.entrada < 20;
            if (this._entrada !== undefined && reciente)
                mostrarRotulo(panel);
            this._entrada = panel.entrada;
        }
        this._indicador?.actualizar(panel);
        this._bocina?.actualizar(panel);
    }

    disable() {
        if (this._idTiempo) {
            GLib.source_remove(this._idTiempo);
            this._idTiempo = null;
        }
        if (this._monitor) {
            this._monitor.disconnect(this._idMonitor);
            this._monitor.cancel();
            this._monitor = null;
        }
        this._indicador?.destroy();
        this._bocina?.destroy();
        this._indicador = null;
        this._bocina = null;
    }
}
