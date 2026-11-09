// Dashboard en tiempo real (Etapa 17 — Historia 004): valores actuales de cada circuito
// de un tablero, que se actualizan solos por WebSocket, con alarmas abiertas y aviso de datos antiguos.
import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api.js'
import { Aviso } from '../components/ui.jsx'
import useTableroEnVivo from '../hooks/useTableroEnVivo.js'

const ANTIGUO_MS = 5 * 60 * 1000   // igual que el vigilante: 5 min sin datos = equipo desconectado
const PUNTOS_TENDENCIA = 60        // muestras que guarda la mini-curva de cada circuito
const ahoraMs = () => Date.now()
const SEVERIDAD = { leve: 'leve', moderada: 'moderada', critica: 'crítica' }
// La alarma abierta más grave de un circuito (crítica primero), o undefined si no tiene.
const alarmaDe = (alarmas, circuitoId) => {
  const delCircuito = alarmas.filter((a) => a.circuito_id === circuitoId)
  return delCircuito.find((a) => a.severidad === 'critica') ?? delCircuito[0]
}

const fases = (m, campo) => ['a', 'b', 'c'].map((f) => m?.[`${campo}_${f}`]).filter((v) => v != null)
const corrienteMayor = (m) => (fases(m, 'corriente').length ? Math.max(...fases(m, 'corriente')) : null)
const numero = (v, dec = 1) => (v == null ? '—' : v.toLocaleString('es-CL', { minimumFractionDigits: dec, maximumFractionDigits: dec }))

function hace(ms) {
  if (ms == null) return 'nunca'
  const s = Math.max(0, Math.round(ms / 1000))
  if (s < 60) return `hace ${s} s`
  if (s < 3600) return `hace ${Math.floor(s / 60)} min`
  return `hace ${Math.floor(s / 3600)} h`
}

// Indicador de conexión: siempre punto + texto (nunca solo color).
const ESTADOS = {
  conectando: { texto: 'Conectando…', clase: 'bg-slate-400' },
  en_vivo: { texto: 'En vivo', clase: 'bg-emerald-500' },
  reconectando: { texto: 'Reconectando…', clase: 'bg-amber-500' },
  sin_acceso: { texto: 'Sin acceso a este tablero', clase: 'bg-red-500' },
}

// Mini-curva de la corriente reciente (sin ejes: solo la tendencia).
function Tendencia({ valores }) {
  if (valores.length < 2) return <div className="h-10" />
  const min = Math.min(...valores), max = Math.max(...valores), rango = max - min || 1
  const puntos = valores.map((v, i) => `${(i / (valores.length - 1)) * 200},${38 - ((v - min) / rango) * 34}`).join(' ')
  return (
    <svg viewBox="0 0 200 40" className="h-10 w-full" preserveAspectRatio="none" aria-hidden="true">
      <polyline points={puntos} fill="none" stroke="#2a78d6" strokeWidth="2" vectorEffect="non-scaling-stroke"
        strokeLinejoin="round" strokeLinecap="round" />
    </svg>
  )
}

// Temperatura ESTIMADA del cable (Etapa 19a): la calcula el backend con la corriente y la
// ampacidad del calibre (no es una medición). Ámbar desde el 80 % de la máxima de la aislación.
function TemperaturaCable({ circuito, medicion, tMax }) {
  if (!circuito.ampacidad_cable) {
    return <p className="text-xs text-slate-400">Sin calibre de cable: asígnalo en Circuitos para estimar su temperatura.</p>
  }
  const t = medicion?.temperatura_conductor
  if (t == null) return null
  const alta = t >= 0.8 * tMax
  const color = t >= tMax ? 'text-red-700' : alta ? 'text-amber-700' : 'text-slate-900'
  return (
    <p className="flex justify-between text-sm" title={`Estimada: ambiente + (máx. aislación ${numero(tMax, 0)} °C − ambiente) · (I / ${numero(circuito.ampacidad_cable, 0)} A)²`}>
      <span className="text-slate-500">Temp. cable (estimada) · {numero(circuito.calibre_cable_mm2)} mm²</span>
      <strong className={`tabular-nums ${color}`}>{numero(t)} °C{alta && ' ⚠'}</strong>
    </p>
  )
}

// Carga respecto del automático: barra + porcentaje (ámbar desde 80 %, rojo desde 100 %).
function Carga({ corriente, automatico }) {
  if (corriente == null || !automatico) return null
  const pct = (corriente / automatico) * 100
  const color = pct >= 100 ? 'bg-red-600' : pct >= 80 ? 'bg-amber-500' : 'bg-slate-500'
  return (
    <div>
      <div className="flex justify-between text-xs text-slate-500">
        <span>Carga del automático ({numero(automatico, 0)} A)</span>
        <span className="font-medium text-slate-700">{numero(pct, 0)} %{pct >= 80 && ' ⚠'}</span>
      </div>
      <div className="mt-1 h-1.5 overflow-hidden rounded-full bg-slate-100">
        <div className={`h-full rounded-full ${color}`} style={{ width: `${Math.min(pct, 100)}%` }} />
      </div>
    </div>
  )
}

function TarjetaCircuito({ circuito, tendencia, ahora, alarma, tMax }) {
  const m = circuito.ultima
  const edad = m ? ahora - new Date(m.medido_en).getTime() : null
  const antiguo = edad == null || edad > ANTIGUO_MS
  const trifasico = fases(m, 'corriente').length > 1
  return (
    <article className={`space-y-3 rounded-lg bg-white p-4 shadow-sm ${!alarma ? 'ring-1 ring-slate-200' : alarma.severidad === 'critica' ? 'ring-2 ring-red-500' : 'ring-2 ring-amber-500'}`}>
      <header className="flex items-baseline justify-between gap-2">
        <h2 className="font-semibold text-slate-900">{circuito.codigo} <span className="font-normal text-slate-500">{circuito.nombre}</span></h2>
        <span className={`text-xs ${antiguo ? 'font-medium text-amber-700' : 'text-slate-500'}`}>
          {antiguo && m ? '⚠ ' : ''}{m ? hace(edad) : 'sin datos'}
        </span>
      </header>
      {alarma && (
        <p className={`text-xs font-medium ${alarma.severidad === 'critica' ? 'text-red-700' : 'text-amber-700'}`}>
          ⚠ Alarma {SEVERIDAD[alarma.severidad] ?? alarma.severidad} abierta
        </p>
      )}
      <p>
        <span className="text-3xl font-bold tabular-nums text-slate-900">{numero(corrienteMayor(m))}</span>
        <span className="ml-1 text-sm text-slate-500">A{trifasico && ' (fase más cargada)'}</span>
      </p>
      <Tendencia valores={tendencia} />
      <Carga corriente={corrienteMayor(m)} automatico={circuito.corriente_automatico} />
      {m && (
        <table className="w-full text-sm">
          <thead className="text-xs text-slate-500">
            <tr><th className="text-left font-normal">Fase</th><th className="text-right font-normal">Voltaje (V)</th><th className="text-right font-normal">Corriente (A)</th></tr>
          </thead>
          <tbody className="tabular-nums">
            {['a', 'b', 'c'].filter((f) => m[`corriente_${f}`] != null || m[`voltaje_${f}`] != null).map((f) => (
              <tr key={f}><td>{f.toUpperCase()}</td><td className="text-right">{numero(m[`voltaje_${f}`])}</td><td className="text-right">{numero(m[`corriente_${f}`], 2)}</td></tr>
            ))}
          </tbody>
        </table>
      )}
      {m && (
        <p className="flex justify-between border-t border-slate-100 pt-2 text-sm">
          <span className="text-slate-500">Potencia <strong className="tabular-nums text-slate-900">{numero(m.potencia_activa == null ? null : m.potencia_activa / 1000, 2)} kW</strong></span>
          <span className="text-slate-500">Energía <strong className="tabular-nums text-slate-900">{numero(m.energia_kwh, 1)} kWh</strong></span>
        </p>
      )}
      <TemperaturaCable circuito={circuito} medicion={m} tMax={tMax} />
    </article>
  )
}

// Panel de UN tablero. Se monta de nuevo al cambiar de tablero (key), así parte limpio.
function PanelTablero({ tableroId }) {
  const [estadoTablero, setEstadoTablero] = useState(null)
  const [tendencias, setTendencias] = useState({}) // circuito_id → últimas corrientes
  const [error, setError] = useState('')
  const [ahora, setAhora] = useState(ahoraMs)

  // Foto inicial del tablero + los últimos 30 min para las mini-curvas.
  useEffect(() => {
    const hasta = new Date(), desde = new Date(hasta.getTime() - 30 * 60 * 1000)
    const params = new URLSearchParams({ tablero_id: tableroId, desde: desde.toISOString(), hasta: hasta.toISOString() })
    Promise.all([api(`/mediciones/estado-actual?tablero_id=${tableroId}`), api(`/mediciones/historial?${params}`)])
      .then(([estado, historial]) => {
        setEstadoTablero(estado)
        setTendencias(Object.fromEntries(historial.circuitos.map((c) => [c.id, c.puntos.map(corrienteMayor).filter((v) => v != null)])))
      })
      .catch((e) => setError(e.message))
  }, [tableroId])

  // El reloj avanza cada segundo para que "hace X s" esté siempre al día.
  useEffect(() => {
    const reloj = setInterval(() => setAhora(ahoraMs()), 1000)
    return () => clearInterval(reloj)
  }, [])

  // Cada evento del WebSocket actualiza solo lo que cambió.
  const alRecibir = useCallback((evento) => {
    if (evento.tipo === 'medicion') {
      setEstadoTablero((e) => e && {
        ...e,
        circuitos: e.circuitos.map((c) => (c.id === evento.circuito_id ? { ...c, ultima: evento } : c)),
        equipos: e.equipos.map((q) => (q.id === evento.dispositivo_id ? { ...q, ultima_comunicacion: evento.medido_en } : q)),
      })
      const valor = corrienteMayor(evento)
      if (valor != null) {
        setTendencias((t) => ({ ...t, [evento.circuito_id]: [...(t[evento.circuito_id] ?? []), valor].slice(-PUNTOS_TENDENCIA) }))
      }
    } else if (evento.tipo === 'comunicacion') {
      setEstadoTablero((e) => e && { ...e, equipos: e.equipos.map((q) => (q.id === evento.dispositivo_id ? { ...q, ultima_comunicacion: evento.en } : q)) })
    } else if (evento.tipo === 'alarma') {
      setEstadoTablero((e) => e && {
        ...e,
        alarmas_abiertas: evento.accion === 'creada'
          ? [{ id: evento.alarma_id, tipo: evento.alarma_tipo, severidad: evento.severidad, mensaje: evento.mensaje, dispositivo_id: evento.dispositivo_id, circuito_id: evento.circuito_id }, ...e.alarmas_abiertas]
          : e.alarmas_abiertas.filter((a) => a.id !== evento.alarma_id),
      })
    }
  }, [])

  const conexion = useTableroEnVivo(tableroId, alRecibir)
  const indicador = ESTADOS[conexion]

  if (error) return <Aviso>{error}</Aviso>
  if (!estadoTablero) return <p className="text-sm text-slate-500">Cargando…</p>

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <p className="flex items-center gap-2 text-sm font-medium text-slate-700" role="status" aria-live="polite">
          <span className={`inline-block h-2.5 w-2.5 rounded-full ${indicador.clase}`} />{indicador.texto}
        </p>
        <ul className="flex flex-wrap gap-4 text-xs text-slate-500">
          {estadoTablero.equipos.map((q) => {
            const edad = q.ultima_comunicacion ? ahora - new Date(q.ultima_comunicacion).getTime() : null
            return (
              <li key={q.id} className={edad == null || edad > ANTIGUO_MS ? 'font-medium text-amber-700' : ''}>
                {q.modelo} · {q.numero_serie ?? 'sin serie'} — último dato {hace(edad)}
              </li>
            )
          })}
        </ul>
      </div>

      {estadoTablero.alarmas_abiertas.length > 0 && (
        <ul className="space-y-1 rounded-md bg-red-50 p-3 text-sm text-red-900 ring-1 ring-red-200" role="alert">
          {estadoTablero.alarmas_abiertas.map((a) => (
            <li key={a.id}>⚠ <strong>Alarma {SEVERIDAD[a.severidad] ?? a.severidad}:</strong> {a.mensaje ?? a.tipo}</li>
          ))}
          <li className="pt-1 text-xs"><Link to="/alarmas" className="underline">Ver todas las alarmas</Link></li>
        </ul>
      )}

      {estadoTablero.circuitos.length === 0
        ? <p className="text-sm text-slate-500">Este tablero no tiene circuitos registrados.</p>
        : (
          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
            {estadoTablero.circuitos.map((c) => (
              <TarjetaCircuito key={c.id} circuito={c} tendencia={tendencias[c.id] ?? []} ahora={ahora}
                alarma={alarmaDe(estadoTablero.alarmas_abiertas, c.id)} tMax={estadoTablero.temperatura_max_aislacion} />
            ))}
          </div>
        )}
    </div>
  )
}

export default function EnVivo() {
  const [tableros, setTableros] = useState([])
  const [tableroId, setTableroId] = useState('')
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
          <h1 className="text-2xl font-bold text-slate-900">En vivo</h1>
          <p className="mt-1 text-sm text-slate-500">Valores actuales de cada circuito. Se actualizan solos, sin recargar la página.</p>
        </div>
        <label className="text-sm text-slate-700">Tablero
          <select className="mt-1 block rounded-md border border-slate-300 bg-white px-2 py-1.5 text-sm"
            value={tableroId} onChange={(e) => setTableroId(e.target.value)}>
            {tableros.map((t) => <option key={t.id} value={t.id}>{t.codigo} · {t.nombre}</option>)}
          </select>
        </label>
      </header>
      <Aviso>{error}</Aviso>
      {tableroId && <PanelTablero key={tableroId} tableroId={tableroId} />}
    </section>
  )
}
