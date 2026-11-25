// Umbrales de alarma por circuito (Etapa 15 — Historia 005).
// Corriente (máx. A), voltaje (mín. y máx. V) y potencia (máx. kW; la API guarda W).
// Cuando una medición pasa un umbral activo, el sistema abre una alarma sola.
import { useEffect, useState } from 'react'
import { api } from '../api.js'
import { puedeEditar, useAuth } from '../auth.jsx'
import { Aviso, Boton } from '../components/ui.jsx'

// Rango sugerido para 220 V fase-neutro (NTCSD, ±7,5 %).
const VOLTAJE_SUGERIDO = { min: '203.5', max: '236.5' }
const VARIABLES = ['corriente', 'voltaje', 'potencia']
const claseInput = 'w-24 rounded-md border border-slate-300 bg-white px-2 py-1 text-sm disabled:bg-slate-100'
const numero = (v, dec = 1) => v.toLocaleString('es-CL', { maximumFractionDigits: dec })

// Valor que se muestra / escribe: la potencia se ve en kW y se guarda en W.
const aPantalla = (variable, v) => (v == null ? '' : String(variable === 'potencia' ? v / 1000 : v))
const aApi = (variable, texto) => Math.round(Number(texto) * (variable === 'potencia' ? 1000 : 1) * 100) / 100

function resumen(u) {
  if (!u) return <span className="text-slate-400">Sin umbral</span>
  const texto = u.tipo_variable === 'voltaje'
    ? `${numero(u.valor_minimo)} – ${numero(u.valor_umbral)} V`
    : u.tipo_variable === 'potencia' ? `máx. ${numero(u.valor_umbral / 1000, 2)} kW` : `máx. ${numero(u.valor_umbral)} A`
  return u.activo ? texto : <span className="text-slate-400">{texto} (desactivado)</span>
}

// Formulario de UN circuito: una fila por variable, con casilla "Activo".
function FormularioCircuito({ circuito, umbrales, onGuardado, onCancelar }) {
  const [valores, setValores] = useState(() => Object.fromEntries(VARIABLES.map((v) => {
    const u = umbrales[v]
    return [v, { activo: u?.activo ?? false, max: aPantalla(v, u?.valor_umbral), min: aPantalla(v, u?.valor_minimo) }]
  })))
  const [error, setError] = useState('')
  const [ocupado, setOcupado] = useState(false)
  const cambiar = (variable, campo, valor) => setValores((p) => ({ ...p, [variable]: { ...p[variable], [campo]: valor } }))

  function sugeridos() {
    setValores((p) => ({
      ...p,
      voltaje: { activo: true, min: VOLTAJE_SUGERIDO.min, max: VOLTAJE_SUGERIDO.max },
      corriente: circuito.corriente_automatico
        ? { ...p.corriente, activo: true, max: String(circuito.corriente_automatico) } : p.corriente,
    }))
  }

  async function guardar(e) {
    e.preventDefault()
    setError('')
    for (const v of VARIABLES) {
      const f = valores[v]
      if (f.activo && (f.max === '' || (v === 'voltaje' && f.min === ''))) {
        setError(`Completa los valores de ${v} o desmarca "Activo".`)
        return
      }
    }
    setOcupado(true)
    try {
      for (const v of VARIABLES) {
        const f = valores[v], u = umbrales[v]
        const datos = { valor_umbral: f.max === '' ? undefined : aApi(v, f.max) }
        if (v === 'voltaje' && f.min !== '') datos.valor_minimo = aApi(v, f.min)
        if (u) {
          // Ya existe: se edita (si se desmarca "Activo", se desactiva y conserva sus valores).
          const cambios = { activo: f.activo }
          if (f.activo) Object.assign(cambios, datos)
          const igual = cambios.activo === u.activo && (!f.activo
            || (cambios.valor_umbral === u.valor_umbral && (v !== 'voltaje' || cambios.valor_minimo === u.valor_minimo)))
          if (!igual) await api(`/umbrales/${u.id}`, { metodo: 'PATCH', datos: cambios })
        } else if (f.activo) {
          await api('/umbrales', { metodo: 'POST', datos: { circuito_id: circuito.id, tipo_variable: v, ...datos } })
        }
      }
      onGuardado(`Umbrales de ${circuito.codigo} guardados.`)
    } catch (err) {
      setError(err.message)
      onGuardado(null) // recarga igual: parte de los cambios pudo haberse guardado
    } finally {
      setOcupado(false)
    }
  }

  const fila = (v, etiqueta, unidad) => (
    <tr key={v}>
      <td className="py-2 pr-4">
        <label className="flex items-center gap-2">
          <input type="checkbox" checked={valores[v].activo} onChange={(e) => cambiar(v, 'activo', e.target.checked)} />
          {etiqueta}
        </label>
      </td>
      <td className="py-2 pr-4">
        {v === 'voltaje' && (
          <label className="mr-3 text-slate-600">mín.{' '}
            <input type="number" step="any" min="0" className={claseInput} disabled={!valores[v].activo}
              value={valores[v].min} onChange={(e) => cambiar(v, 'min', e.target.value)} />
          </label>
        )}
        <label className="text-slate-600">máx.{' '}
          <input type="number" step="any" min="0" className={claseInput} disabled={!valores[v].activo}
            value={valores[v].max} onChange={(e) => cambiar(v, 'max', e.target.value)} />
        </label>
        <span className="ml-2 text-slate-500">{unidad}</span>
      </td>
    </tr>
  )

  return (
    <form onSubmit={guardar} className="space-y-3 rounded-lg bg-white p-5 shadow-sm ring-1 ring-slate-200">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 className="font-semibold text-slate-900">Umbrales de {circuito.codigo} {circuito.nombre}</h2>
        <Boton type="button" variante="secundario" onClick={sugeridos}>Usar valores sugeridos</Boton>
      </div>
      <p className="text-xs text-slate-500">
        Sugeridos: voltaje {VOLTAJE_SUGERIDO.min.replace('.', ',')} – {VOLTAJE_SUGERIDO.max.replace('.', ',')} V (220 V ±7,5 %, NTCSD)
        {circuito.corriente_automatico ? ` y corriente máx. igual al automático (${numero(circuito.corriente_automatico, 0)} A).` : '.'}
      </p>
      <table className="text-sm"><tbody>
        {fila('corriente', 'Corriente', 'A')}
        {fila('voltaje', 'Voltaje', 'V')}
        {fila('potencia', 'Potencia', 'kW')}
      </tbody></table>
      <Aviso>{error}</Aviso>
      <div className="flex gap-2">
        <Boton type="submit" disabled={ocupado}>{ocupado ? 'Guardando…' : 'Guardar'}</Boton>
        <Boton type="button" variante="secundario" onClick={onCancelar}>Cancelar</Boton>
      </div>
    </form>
  )
}

export default function Umbrales() {
  const { usuario } = useAuth()
  const [tableros, setTableros] = useState([])
  const [tableroId, setTableroId] = useState('')
  const [circuitos, setCircuitos] = useState([])
  const [umbrales, setUmbrales] = useState({}) // circuito_id → { corriente, voltaje, potencia }
  const [editando, setEditando] = useState(null)
  const [error, setError] = useState('')
  const [mensaje, setMensaje] = useState('')
  const [recarga, setRecarga] = useState(0)

  useEffect(() => {
    api('/tableros').then((lista) => {
      setTableros(lista)
      if (lista.length) setTableroId(String(lista[0].id))
    }).catch((e) => setError(e.message))
  }, [])

  // Circuitos del tablero y sus umbrales (se vuelve a pedir al guardar: `recarga`).
  useEffect(() => {
    if (!tableroId) return
    let cancelado = false
    Promise.all([api(`/circuitos?tablero_id=${tableroId}`), api(`/umbrales?tablero_id=${tableroId}`)])
      .then(([circ, lista]) => {
        if (cancelado) return
        const porCircuito = {}
        for (const u of lista) (porCircuito[u.circuito_id] ??= {})[u.tipo_variable] = u
        setCircuitos(circ); setUmbrales(porCircuito)
      })
      .catch((e) => { if (!cancelado) setError(e.message) })
    return () => { cancelado = true }
  }, [tableroId, recarga])

  function elegirTablero(id) {
    setTableroId(id); setEditando(null); setMensaje(''); setError('')
  }

  const editable = puedeEditar(usuario)
  return (
    <section className="max-w-6xl space-y-4">
      <header className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">Umbrales</h1>
          <p className="mt-1 text-sm text-slate-500">Límites de cada circuito. Si una medición los pasa, el sistema abre una alarma.</p>
        </div>
        <label className="w-full text-sm text-slate-700 sm:w-auto">Tablero
          <select className="mt-1 block w-full max-w-full rounded-md border border-slate-300 bg-white px-2 py-1.5 text-sm sm:w-auto"
            value={tableroId} onChange={(e) => elegirTablero(e.target.value)}>
            {tableros.map((t) => <option key={t.id} value={t.id}>{t.codigo} · {t.nombre}</option>)}
          </select>
        </label>
      </header>
      <Aviso>{error}</Aviso>
      <Aviso tipo="exito">{mensaje}</Aviso>

      {editando && (
        <FormularioCircuito key={editando.id} circuito={editando} umbrales={umbrales[editando.id] ?? {}}
          onCancelar={() => setEditando(null)}
          onGuardado={(texto) => { if (texto) { setMensaje(texto); setEditando(null) } setRecarga((n) => n + 1) }} />
      )}

      <div className="overflow-x-auto rounded-lg bg-white shadow-sm ring-1 ring-slate-200">
        <table className="min-w-full divide-y divide-slate-200 text-sm">
          <thead className="bg-slate-50 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">
            <tr>
              <th className="px-4 py-3">Circuito</th>
              <th className="px-4 py-3">Automático</th>
              <th className="px-4 py-3">Corriente</th>
              <th className="px-4 py-3">Voltaje</th>
              <th className="px-4 py-3">Potencia</th>
              {editable && <th className="px-4 py-3 text-right">Acciones</th>}
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {circuitos.length === 0 && (
              <tr><td colSpan={6} className="px-4 py-6 text-center text-slate-500">Este tablero no tiene circuitos activos.</td></tr>
            )}
            {circuitos.map((c) => (
              <tr key={c.id}>
                <td className="px-4 py-3">{c.codigo} <span className="text-slate-500">{c.nombre}</span></td>
                <td className="px-4 py-3 tabular-nums">{c.corriente_automatico ? `${numero(c.corriente_automatico, 0)} A` : '—'}</td>
                {VARIABLES.map((v) => <td key={v} className="px-4 py-3 tabular-nums">{resumen(umbrales[c.id]?.[v])}</td>)}
                {editable && (
                  <td className="px-4 py-3 text-right">
                    <Boton variante="secundario" onClick={() => { setMensaje(''); setEditando(c) }}>Editar</Boton>
                  </td>
                )}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  )
}
