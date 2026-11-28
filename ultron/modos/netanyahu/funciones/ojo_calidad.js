// Calidad por pestaña, antes de iniciar Cesium y cargar las capas.
export const opcionesOjo = new URLSearchParams(globalThis.location?.search);
export const esUltron = opcionesOjo.has('ultronCalidad');

export function webglPorSoftware() {
  const gl = globalThis.document?.createElement('canvas').getContext('webgl2');
  if (!gl) return true;
  try {
    const info = gl.getExtension('WEBGL_debug_renderer_info');
    const renderer = gl.getParameter(info?.UNMASKED_RENDERER_WEBGL ?? gl.RENDERER);
    if (/swiftshader|llvmpipe|softpipe|swrast|software|lavapipe|basic render|warp/i.test(renderer))
      return true;
    if (info) return false;
  } finally {
    gl.getExtension('WEBGL_lose_context')?.loseContext();
  }
  // Algunos navegadores ocultan el renderer aunque permitan obtener WebGL.
  const acelerado = document.createElement('canvas').getContext('webgl2', {
    failIfMajorPerformanceCaveat: true,
  });
  acelerado?.getExtension('WEBGL_lose_context')?.loseContext();
  return !acelerado;
}

const solicitada = opcionesOjo.get('ultronCalidad');
export const calidadOjo = !esUltron ? null :
  ['baja', 'media', 'alta'].includes(solicitada) ? solicitada :
  webglPorSoftware() ? 'baja' : 'alta';
export const ojoLigero = calidadOjo === 'baja';
