"""Parche local y reversible para la copia de God's Eye View."""

from difflib import unified_diff
from pathlib import Path

from ultron.nucleo.ejecutor import Ejecutor

from .comun import fallo

VERSION = "2"
CALIDAD = Path(__file__).with_name("ojo_calidad.js")


def _importar(ruta: str, nombres: str) -> tuple[str, str]:
    return "", f"import {{ {nombres} }} from '{ruta}/ultronCalidad.js';\n"


EDICIONES = {
    "src/render/cesium/applicationViewer.js": (
        _importar("../..", "calidadOjo, ojoLigero"),
        ("msaaSamples: msaa || 1,", "msaaSamples: ojoLigero ? 1 : msaa || 1,"),
        (
            "    viewer.targetFrameRate = frameRateCap() || undefined;",
            "    viewer.targetFrameRate = frameRateCap() || undefined;\n"
            "    if (calidadOjo) viewer.resolutionScale = { baja: 0.55, media: 0.8, alta: 1 }"
            "[calidadOjo];\n"
            "    if (ojoLigero) viewer.scene.postProcessStages.fxaa.enabled = false;",
        ),
    ),
    "src/layers/satellites/policy.js": (
        _importar("../..", "ojoLigero"),
        ("export const CATALOG_GROUPS = [", "const grupos = ["),
        (
            "  { tag: 'geo', path: 'geo' },\n];",
            "  { tag: 'geo', path: 'geo' },\n];\n"
            "export const CATALOG_GROUPS = ojoLigero ? grupos.slice(0, 2) : grupos;",
        ),
    ),
    "src/layers/satellites/catalog.js": (
        _importar("../..", "ojoLigero"),
        (
            "    if (!layerState._viewer || !layerState._pointCollection)",
            "    if (ojoLigero) return { status: 'source-unavailable', reason: 'calidad baja' };\n"
            "    if (!layerState._viewer || !layerState._pointCollection)",
        ),
    ),
    "src/layers/traffic/policy.js": (
        _importar("../..", "calidadOjo"),
        ("export const MAX_DOTS = 6000;",
         "export const MAX_DOTS = ({ baja: 900, media: 3800, alta: 7200 })[calidadOjo] ?? 6000;"),
        ("    400,", "    calidadOjo === 'baja' ? 120 : 400,"),
        ("  residential: 5, // ~18 km/h", "  residential: calidadOjo ? 7 : 5, // ~25 km/h"),
    ),
    "src/layers/traffic/model.js": (
        _importar("../..", "calidadOjo"),
        (
            "    const mult =\n      (DENSITY_MULT",
            "    // Las vías urbanas suman densidad solo en el modelo sin TomTom.\n"
            "    if (calidadOjo && !layerState._liveMode && clearance < 5000 &&\n"
            "        ['primary', 'secondary', 'tertiary', 'residential'].includes(road.type))\n"
            "      spacing *= calidadOjo === 'baja' ? 0.9 : 0.55;\n"
            "    const mult =\n      (DENSITY_MULT",
        ),
        (
            "      loadingLabel: statusUnavailable\n",
            "      loadingLabel: calidadOjo ? 'SIMULADO · OpenStreetMap' : statusUnavailable\n",
        ),
    ),
    "src/ui/visualEffects.js": (
        _importar("..", "ojoLigero"),
        ("    if (this.stopped || this.stageEntries.length) return;",
         "    if (ojoLigero || this.stopped || this.stageEntries.length) return;"),
        ("    if (this.stopped || this.sharpenStage) return;",
         "    if (ojoLigero || this.stopped || this.sharpenStage) return;"),
    ),
    "src/ui/visualSettings.js": (
        _importar("..", "ojoLigero"),
        ("      typeof styleName !== 'string' ||",
         "      (ojoLigero && styleName !== 'normal') ||\n"
         "      typeof styleName !== 'string' ||"),
    ),
    "src/styles/surveillance.js": (
        ("vec3(0.16, 1.0, 0.22)", "vec3(0.43, 0.66, 1.0)"),
    ),
    "src/styles/retro.js": (
        ("vec3(1.02, 1.0, 0.94)", "vec3(0.64, 0.83, 1.15)"),
    ),
    "src/styles/thermal.js": (
        ("hud += tempHud * 0.8;", "/* Ultron: se omite la lectura térmica ficticia. */"),
        ("thermalColor *= lensShading;",
         "thermalColor *= mix(vec3(0.35, 0.66, 1.0), vec3(1.0), thermalColor);\n"
         "      thermalColor *= lensShading;"),
    ),
    "server/providers/cctv/catalog.js": (
        (
            "const LIVE_PACKS = [",
            """function cargarUltron(sourceRoot, nombre) {
  try {
    const catalogo = JSON.parse(fs.readFileSync(
      path.join(sourceRoot, 'config', `ultron-${nombre}.json`), 'utf8',
    ));
    return Array.isArray(catalogo) ? catalogo : [];
  } catch {
    return [];
  }
}
const LIVE_PACKS = [
  { name: 'ultron-dgt', enabled: () => true,
    load: ({ sourceRoot }) => cargarUltron(sourceRoot, 'dgt') },
  { name: 'ultron-madrid', enabled: () => true,
    load: ({ sourceRoot }) => cargarUltron(sourceRoot, 'madrid') },""",
        ),
    ),
    "server/providers/cctv/media.js": (
        ("const CCTV_PINNED_PREFIXES_BY_HOST = new Map();\nfor (const prefix of [",
         "const CCTV_PINNED_PREFIXES_BY_HOST = new Map();\nfor (const prefix of [\n"
         "  'https://etraffic.dgt.es/camarasEtraffic/',\n"
         "  'https://informo.madrid.es/informo/Camaras/',"),
    ),
    "server/providers/cctv.js": (
        ("        const upstreamImage =\n          source?.pack === 'world-cameras'",
         "        const ultron = ['ultron-dgt', 'ultron-madrid'].includes(source?.pack);\n"
         "        const upstreamImage =\n          ultron || source?.pack === 'world-cameras'"),
        ("          forwarded || !source", "          ultron || forwarded || !source"),
    ),
}


def generar_parche(destino: Path) -> str:
    """Exige coincidencias únicas para detectar cambios incompatibles del original."""
    parche = []
    for nombre, ediciones in EDICIONES.items():
        original = (destino / nombre).read_text(encoding="utf-8")
        nuevo = original
        for ancla, reemplazo in ediciones:
            if not ancla:
                nuevo = reemplazo + nuevo
            elif nuevo.count(ancla) == 1:
                nuevo = nuevo.replace(ancla, reemplazo)
            else:
                raise ValueError(f"God’s Eye View cambió el archivo {nombre}.")
        parche.extend(unified_diff(original.splitlines(keepends=True),
                                   nuevo.splitlines(keepends=True), f"a/{nombre}", f"b/{nombre}"))
    nombre = "src/ultronCalidad.js"
    parche.append(f"diff --git a/{nombre} b/{nombre}\nnew file mode 100644\n")
    parche.extend(unified_diff([], CALIDAD.read_text(encoding="utf-8").splitlines(keepends=True),
                               "/dev/null", f"b/{nombre}"))
    return "".join(parche)


def _archivo(destino: Path) -> Path:
    return destino / ".git" / "ultron-ojo.patch"


def _git(ej: Ejecutor, destino: Path, *opciones: str) -> bool:
    resultado = ej.run(["git", "apply", *opciones, str(_archivo(destino).resolve())],
                       directorio=destino, check=False)
    return resultado.ok


def quitar_parche(ej: Ejecutor, destino: Path) -> None:
    """Retira solo los cambios de Ultron para permitir una actualización."""
    if not _archivo(destino).is_file() and not ej.simular:
        return
    if _git(ej, destino, "--reverse", "--check"):
        if not _git(ej, destino, "--reverse"):
            fallo("No se pudo retirar el parche de Ojo de Dios.")
    elif not _git(ej, destino, "--check"):
        fallo("La copia de Ojo de Dios tiene cambios que impiden retirar el parche.")
    ej.borrar(_archivo(destino))


def aplicar_parche(ej: Ejecutor, destino: Path) -> None:
    """Guarda el diff antes de aplicarlo para poder recuperar una instalación cortada."""
    if ej.simular:
        ej.escribir(_archivo(destino), "")
    else:
        if _archivo(destino).is_file() and _git(ej, destino, "--reverse", "--check"):
            return
        try:
            parche = generar_parche(destino)
        except (OSError, ValueError) as error:
            fallo(f"No se pudo preparar el parche de Ojo de Dios. {error}")
        ej.escribir(_archivo(destino), parche)
    if not _git(ej, destino, "--check") or not _git(ej, destino):
        fallo("No se pudo aplicar el parche de Ojo de Dios.")
