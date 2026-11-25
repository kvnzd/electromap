// Alarmas de un tablero (Etapa 15 — Historia 005): abiertas, resueltas o todas.
// La lista se actualiza sola (WebSocket) cuando el sistema abre o cierra una alarma.
// Un editor puede cerrar a mano una alarma abierta; queda registrado quién lo hizo.
import { useCallback, useEffect, useState } from 'react'
import { api } from '../api.js'
import { puedeEditar, useAuth } from '../auth.jsx'
import { Aviso, Boton } from '../components/ui.jsx'
import useTableroEnVivo from '../hooks/useTableroEnVivo.js'

const ESTADOS = [
  { id: 'abiertas', texto: 'Abiertas' },
  { id: 'resueltas', texto: 'Resueltas' },
  { id: 'todas', texto: 'Todas' },
]
const TIPOS = {
  umbral_corriente: 'Corriente sobre el umbral',
  umbral_voltaje: 'Voltaje fuera de rango',
  umbral_potencia: 'Potencia sobre el umbral',
  dispositivo_offline: 'Equipo desconectado',
  fase_caida: 'Fase caída',
  temperatura_alta: 'Temperatura alta',
  otro: 'Otra',
}
// Severidad: siempre texto + color (nunca solo color).
const SEVERIDAD = {
  critica: { texto: 'Crítica', clase: 'bg-red-100 text-red-800' },
  moderada: { texto: 'Moderada', clase: 'bg-amber-100 text-amber-800' },
  leve: { texto: 'Leve', clase: 'bg-slate-200 text-slate-700' },
}
const fecha = (iso) => (iso ? new Date(iso).toLocaleString('es-CL', { dateStyle: 'short', timeStyle: 'short' }) : '—')

function TablaAlarmas({ tableroId, estado }) {
  const { usuario } = useAuth()
  const [alarmas, setAlarmas] = useState(null)
  const [circuitos, setCircuitos] = useState({})
  const [error, setError] = useState('')
  const [mensaje, setMensaje] = useState('')
  const [recarga, setRecarga] = useState(0)
  const recargar = useCallback(() => setRecarga((n) => n + 1), [])

  useEffect(() => {
    let cancelado = false
    Promise.all([
      api(`/alarmas?tablero_id=${tableroId}&estado=${estado}`),
      api(`/circuitos?tablero_id=${tableroId}&incluir_inactivos=true`),
    ]).then(([lista, circ]) => {
      if (cancelado) return
      setAlarmas(lista)
      setCircuitos(Object.fromEntries(circ.map((c) => [c.id, c])))
    }).catch((e) => { if (!cancelado) setError(e.message) })
    return () => { cancelado = true }
  }, [tableroId, estado, recarga])

  // Cuando el sistema abre o cierra una alarma de este tablero, la lista se vuelve a pedir.
  const conexion = useTableroEnVivo(tableroId, useCallback((evento) => {
    if (evento.tipo === 'alarma') recargar()
  }, [recargar]))

  async function resolver(alarma) {
    if (!window.confirm('¿Cerrar esta alarma? Si el problema sigue, el sistema abrirá una nueva.')) return
    setError(''); setMensaje('')
    try {
      await api(`/alarmas/${alarma.id}/resolver`, { metodo: 'PATCH' })
      setMensaje('Alarma cerrada.')
      recargar()
    } catch (e) {
      setError(e.message)
    }
  }

  if (error) return <Aviso>{error}</Aviso>
  if (!alarmas) return <p className="text-sm text-slate-500">Cargando…</p>
  const editable = puedeEditar(usuario)

  return (
    <div className="space-y-3">
      <p className="text-xs text-slate-500" role="status">
        {conexion === 'en_vivo' ? 'Se actualiza sola cuando el sistema abre o cierra una alarma.' : 'Conectando para actualizar en vivo…'}
      </p>
      <Aviso tipo="exito">{mensaje}</Aviso>
      <div className="overflow-x-auto rounded-lg bg-white shadow-sm ring-1 ring-slate-200">
        <table className="min-w-full divide-y divide-slate-200 text-sm">
          <thead className="bg-slate-50 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">
            <tr>
              <th className="px-4 py-3">Inicio</th>
              <th className="px-4 py-3">Circuito</th>
              <th className="px-4 py-3">Tipo</th>
              <th className="px-4 py-3">Severidad</th>
              <th className="px-4 py-3">Detalle</th>
              <th className="px-4 py-3">Estado</th>
              {editable && <th className="px-4 py-3 text-right">Acciones</th>}
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {alarmas.length === 0 && (
              <tr><td colSpan={7} className="px-4 py-6 text-center text-slate-500">
                {estado === 'abiertas' ? 'Sin alarmas abiertas. Todo en orden.' : 'Sin alarmas.'}
              </td></tr>
            )}
            {alarmas.map((a) => {
              const c = circuitos[a.circuito_id]
              const sev = SEVERIDAD[a.severidad] ?? { texto: a.severidad, clase: 'bg-slate-200 text-slate-700' }
              return (
                <tr key={a.id} className={a.resuelto ? 'text-slate-500' : ''}>
                  <td className="whitespace-nowrap px-4 py-3 tabular-nums">{fecha(a.generado_en)}</td>
                  <td className="px-4 py-3">{c ? `${c.codigo} ${c.nombre}` : `Equipo #${a.dispositivo_id}`}</td>
                  <td className="px-4 py-3">{TIPOS[a.tipo] ?? a.tipo}</td>
                  <td className="px-4 py-3"><span className={`rounded-full px-2 py-0.5 text-xs font-medium ${sev.clase}`}>{sev.texto}</span></td>
                  <td className="px-4 py-3">{a.mensaje ?? '—'}</td>
                  <td className="px-4 py-3">
                    {a.resuelto
                      ? <>Resuelta {fecha(a.resuelto_en)}<br /><span className="text-xs">{a.resuelto_por_nombre ? `por ${a.resuelto_por_nombre}` : 'por el sistema'}</span></>
                      : <strong className="text-red-700">Abierta</strong>}
                  </td>
                  {editable && (
                    <td className="px-4 py-3 text-right">
                      {!a.resuelto && <Boton variante="secundario" onClick={() => resolver(a)}>Cerrar</Boton>}
                    </td>
                  )}
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    </div>
  )
}

export default function Alarmas() {
  const [tableros, setTableros] = useState([])
  const [tableroId, setTableroId] = useState('')
  const [estado, setEstado] = useState('abiertas')
  const [error, setError] = useState('')

  useEffect(() => {
    api('/tableros').then((lista) => {
      setTableros(lista)
      if (lista.length) setTableroId(String(lista[0].id))
    }).catch((e) => setError(e.message))
  }, [])

  return (
    <section className="max-w-6xl space-y-4">
      <header className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">Alarmas</h1>
          <p className="mt-1 text-sm text-slate-500">Las abre y las cierra el sistema según los umbrales y la comunicación de los equipos.</p>
        </div>
        <label className="w-full text-sm text-slate-700 sm:w-auto">Tablero
          <select className="mt-1 block w-full max-w-full rounded-md border border-slate-300 bg-white px-2 py-1.5 text-sm sm:w-auto"
            value={tableroId} onChange={(e) => setTableroId(e.target.value)}>
            {tableros.map((t) => <option key={t.id} value={t.id}>{t.codigo} · {t.nombre}</option>)}
          </select>
        </label>
      </header>
      <div className="flex gap-1" role="tablist">
        {ESTADOS.map((e) => (
          <button key={e.id} role="tab" aria-selected={estado === e.id} onClick={() => setEstado(e.id)}
            className={`rounded-md px-3 py-1.5 text-sm ${estado === e.id ? 'bg-slate-900 font-medium text-white' : 'bg-white text-slate-700 ring-1 ring-slate-300 hover:bg-slate-50'}`}>
            {e.texto}
          </button>
        ))}
      </div>
      <Aviso>{error}</Aviso>
      {tableroId && <TablaAlarmas key={tableroId} tableroId={tableroId} estado={estado} />}
    </section>
  )
}
