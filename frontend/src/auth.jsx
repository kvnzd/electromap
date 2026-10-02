// Estado de la sesión: quién está conectado y qué puede hacer.
import { createContext, useCallback, useContext, useEffect, useState } from 'react'
import { api, borrarToken, guardarToken, leerToken } from './api.js'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [usuario, setUsuario] = useState(null)
  const [cargando, setCargando] = useState(Boolean(leerToken()))

  const cerrarSesion = useCallback(() => {
    borrarToken()
    setUsuario(null)
  }, [])

  // Si había una sesión guardada, se valida contra el backend al abrir la página.
  useEffect(() => {
    if (!leerToken()) return
    api('/auth/me')
      .then(setUsuario)
      .catch(cerrarSesion)
      .finally(() => setCargando(false))
  }, [cerrarSesion])

  // Si el backend responde 401 en cualquier pantalla, se cierra la sesión.
  useEffect(() => {
    window.addEventListener('electromap:sesion-expirada', cerrarSesion)
    return () => window.removeEventListener('electromap:sesion-expirada', cerrarSesion)
  }, [cerrarSesion])

  async function iniciarSesion(nombreUsuario, password) {
    const r = await api('/auth/login', {
      metodo: 'POST',
      formulario: { username: nombreUsuario, password },
    })
    guardarToken(r.access_token)
    setUsuario(r.usuario)
  }

  return (
    <AuthContext.Provider value={{ usuario, cargando, iniciarSesion, cerrarSesion }}>
      {children}
    </AuthContext.Provider>
  )
}

// eslint-disable-next-line react-refresh/only-export-components
export function useAuth() {
  return useContext(AuthContext)
}

// Mismas reglas que el backend (el backend es quien decide; esto solo oculta botones).
// eslint-disable-next-line react-refresh/only-export-components
export function puedeEditar(usuario) {
  if (!usuario || usuario.rol === 'cliente') return false
  return usuario.rol === 'vsc' || usuario.puede_editar
}
