// Comunicación con el backend (FastAPI).
// La dirección del backend se puede cambiar con la variable VITE_API_URL.
export const API_URL = import.meta.env.VITE_API_URL ?? 'http://127.0.0.1:8000'

const CLAVE_TOKEN = 'electromap_token'

export const leerToken = () => sessionStorage.getItem(CLAVE_TOKEN)
export const guardarToken = (token) => sessionStorage.setItem(CLAVE_TOKEN, token)
export const borrarToken = () => sessionStorage.removeItem(CLAVE_TOKEN)

// Error con el código HTTP y un mensaje legible para mostrar en pantalla.
export class ErrorApi extends Error {
  constructor(status, mensaje) {
    super(mensaje)
    this.status = status
  }
}

function mensajeDeError(cuerpo) {
  const detalle = cuerpo?.detail
  if (typeof detalle === 'string') return detalle
  // Errores de validación (422): lista de campos con problemas.
  if (Array.isArray(detalle)) {
    return detalle.map((d) => `${d.loc?.at(-1) ?? 'dato'}: ${d.msg}`).join(' · ')
  }
  return 'Error inesperado'
}

// Hace una petición al backend agregando el token de sesión.
export async function api(ruta, { metodo = 'GET', datos, formulario } = {}) {
  const headers = {}
  const token = leerToken()
  if (token) headers.Authorization = `Bearer ${token}`

  let body
  if (formulario) {
    body = new URLSearchParams(formulario) // login: formato de formulario (OAuth2)
  } else if (datos !== undefined) {
    headers['Content-Type'] = 'application/json'
    body = JSON.stringify(datos)
  }

  let respuesta
  try {
    respuesta = await fetch(`${API_URL}${ruta}`, { method: metodo, headers, body })
  } catch {
    throw new ErrorApi(0, 'No se pudo conectar con el servidor. ¿Está encendido el backend?')
  }

  const cuerpo = respuesta.status === 204 ? null : await respuesta.json().catch(() => null)
  if (!respuesta.ok) {
    if (respuesta.status === 401 && ruta !== '/auth/login') {
      // Sesión vencida o cuenta desactivada: se avisa al resto de la app.
      window.dispatchEvent(new Event('electromap:sesion-expirada'))
    }
    throw new ErrorApi(respuesta.status, mensajeDeError(cuerpo))
  }
  return cuerpo
}
