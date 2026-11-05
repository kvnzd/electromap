// Conexión en tiempo real con un tablero (WebSocket /ws/tableros/{id}, Etapa 16).
// - Envía el token de la sesión como primer mensaje (no va en la URL).
// - Si la conexión se corta, reintenta sola: espera 1 s, 2 s, 5 s y luego cada 10 s.
// - 4401 (sesión inválida): cierra la sesión. 4403 (sin acceso): no reintenta.
// Cada mensaje recibido se entrega a `alRecibir(evento)`.
import { useEffect, useRef, useState } from 'react'
import { API_URL, leerToken } from '../api.js'

const ESPERAS_MS = [1000, 2000, 5000, 10000]
const URL_WS = API_URL.replace(/^http/, 'ws') // http → ws, https → wss

export default function useTableroEnVivo(tableroId, alRecibir) {
  const [estado, setEstado] = useState('conectando') // conectando | en_vivo | reconectando | sin_acceso
  const manejador = useRef(alRecibir)

  // Siempre usa la versión más reciente de alRecibir sin reconectar.
  useEffect(() => { manejador.current = alRecibir })

  useEffect(() => {
    let socket = null
    let intento = 0
    let temporizador = null
    let terminado = false

    function conectar() {
      socket = new WebSocket(`${URL_WS}/ws/tableros/${tableroId}`)
      socket.onopen = () => socket.send(JSON.stringify({ token: leerToken() }))
      socket.onmessage = (e) => {
        const evento = JSON.parse(e.data)
        if (evento.tipo === 'conectado') { intento = 0; setEstado('en_vivo') }
        manejador.current?.(evento)
      }
      socket.onclose = (e) => {
        if (terminado) return
        if (e.code === 4401) { window.dispatchEvent(new Event('electromap:sesion-expirada')); return }
        if (e.code === 4403) { setEstado('sin_acceso'); return }
        setEstado('reconectando')
        temporizador = setTimeout(conectar, ESPERAS_MS[Math.min(intento++, ESPERAS_MS.length - 1)])
      }
    }

    conectar()
    return () => { terminado = true; clearTimeout(temporizador); socket?.close() }
  }, [tableroId])

  return estado
}
