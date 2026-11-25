// Historial de mediciones (Etapa 18 — Historia 006): elegir tablero y rango de fechas,
// ver la evolución de corriente / voltaje / potencia por circuito y un resumen del período.
import { useCallback, useEffect, useState } from 'react'
import { api } from '../api.js'
import GraficoLineas from '../components/GraficoLineas.jsx'
import { Aviso, Boton } from '../components/ui.jsx'

const HORA = 3600 * 1000
// Paleta categórica validada (daltonismo y contraste). Orden fijo: el color sigue al circuito.
const COLORES_SERIES = ['#2a78d6', '#eb6834', '#1baf7a', '#eda100', '#e87ba4', '#008300', '#6250d6', '#e34948']
const RANGOS = [
  { id: '6h', texto: 'Últimas 6 h', ms: 6 * HORA },
  { id: '24h', texto: 'Últimas 24 h', ms: 24 * HORA },
  { id: '3d', texto: 'Últimos 3 días', ms: 72 * HORA },
  { id: '7d', texto: 'Últimos 7 días', ms: 168 * HORA },
]

// Qué se grafica de cada variable. En circuitos trifásicos:
// corriente = la fase más cargada; voltaje = promedio de las fases; potencia = total.
const fases = (p, campo) => ['a', 'b', 'c'].map((f) => p[`${campo}_${f}`]).filter((v) => v != null)
const VARIABLES = {
  corriente: { texto: 'Corriente', unidad: 'A', valor: (p) => (fases(p, 'corriente').length ? Math.max(...fases(p, 'corriente')) : null) },
  voltaje: { texto: 'Voltaje', unidad: 'V', valor: (p) => { const v = fases(p, 'voltaje'); return v.length ? v.reduce((a, b) => a + b, 0) / v.length : null } },
  potencia: { texto: 'Potencia', unidad: 'kW', valor: (p) => (p.potencia_activa == null ? null : p.potencia_activa / 1000) },
}

// "2026-11-05T13:44" (lo que usan los campos datetime-local) en hora local.
const aCampoLocal = (fecha) => {
  const d = new Date(fecha.getTime() - fecha.getTimezoneOffset() * 60000)
  return d.toISOString().slice(0, 16)
}
// [desde, hasta] para los últimos `ms` milisegundos, en formato de los campos de fecha.
const ultimos = (ms) => {
  const ahora = new Date()
  return [aCampoLocal(new Date(ahora.getTime() - ms)), aCampoLocal(ahora)]
}
const numero = (v, dec = 2) => (v == null ? '—' : v.toLocaleString('es-CL', { maximumFractionDigits: dec }))

export default function Historial() {
  const [tableros, setTableros] = useState([])
  const [tableroId, setTableroId] = useState('')
  const [rango, setRango] = useState('24h')
  const [desde, setDesde] = useState(() => ultimos(24 * HORA)[0])
  const [hasta, setHasta] = useState(() => ultimos(24 * HORA)[1])
  const [variable, setVariable] = useState('corriente')
  const [datos, setDatos] = useState(null)
  const [cargando, setCargando] = useState(false)
  const [error, setError] = useState('')

  const consultar = useCallback(async (idTablero, desdeLocal, hastaLocal) => {
    if (!idTablero) return
    setCargando(true); setError('')
    try {
      const params = new URLSearchParams({
        tablero_id: idTablero,
        desde: new Date(desdeLocal).toISOString(),
        hasta: new Date(hastaLocal).toISOString(),
      })
      setDatos(await api(`/mediciones/historial?${params}`))
    } catch (e) {
      setError(e.message)
    } finally {
      setCargando(false)
    }
  }, [])

  // Al abrir la página: carga los tableros visibles y consulta el primero (últimas 24 h).
  useEffect(() => {
    api('/tableros').then((lista) => {
      setTableros(lista)
      if (lista.length) {
        const [d, h] = ultimos(24 * HORA)
        setTableroId(String(lista[0].id))
        consultar(String(lista[0].id), d, h)
      }
    }).catch((e) => setError(e.message))
  }, [consultar])

  function elegirTablero(id) {
    setTableroId(id)
    consultar(id, desde, hasta)
  }

  function elegirRango(r) {
    const [nuevoDesde, nuevoHasta] = ultimos(r.ms)
    setRango(r.id); setDesde(nuevoDesde); setHasta(nuevoHasta)
    consultar(tableroId, nuevoDesde, nuevoHasta)
  }

  const def = VARIABLES[variable]
  const series = (datos?.circuitos ?? []).map((c, i) => ({
    id: c.id,
    nombre: c.codigo,
    color: COLORES_SERIES[i % COLORES_SERIES.length],
    puntos: c.puntos.map((p) => ({ t: new Date(p.t).getTime(), v: def.valor(p) })),
  }))
  const unDiaOMenos = datos && new Date(datos.hasta) - new Date(datos.desde) <= 24 * HORA
  const formatoHora = (t, completo = false) => new Date(t).toLocaleString('es-CL', completo || !unDiaOMenos
    ? { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' }
    : { hour: '2-digit', minute: '2-digit' })

  const claseCampo = 'rounded-md border border-slate-300 bg-white px-2 py-1.5 text-sm'
  return (
    <section className="max-w-6xl space-y-4">
      <header>
        <h1 className="text-2xl font-bold text-slate-900">Historial</h1>
        <p className="mt-1 text-sm text-slate-500">
          Mediciones de cada circuito en un rango de fechas. Los puntos son promedios del intervalo indicado.
        </p>
      </header>

      {/* Filtros: una fila, sobre todo lo que filtran */}
      <div className="flex flex-wrap items-end gap-3 rounded-lg bg-white p-4 shadow-sm ring-1 ring-slate-200">
        <label className="w-full text-sm text-slate-700 sm:w-auto">Tablero
          <select className={`${claseCampo} mt-1 block w-full max-w-full sm:w-auto`} value={tableroId} onChange={(e) => elegirTablero(e.target.value)}>
            {tableros.map((t) => <option key={t.id} value={t.id}>{t.codigo} · {t.nombre}</option>)}
          </select>
        </label>
        <div className="flex gap-1">
          {RANGOS.map((r) => (
            <Boton key={r.id} variante={rango === r.id ? 'primario' : 'secundario'} onClick={() => elegirRango(r)}>{r.texto}</Boton>
          ))}
        </div>
        <label className="text-sm text-slate-700">Desde
          <input type="datetime-local" className={`${claseCampo} mt-1 block`} value={desde}
            onChange={(e) => { setDesde(e.target.value); setRango('') }} />
        </label>
        <label className="text-sm text-slate-700">Hasta
          <input type="datetime-local" className={`${claseCampo} mt-1 block`} value={hasta}
            onChange={(e) => { setHasta(e.target.value); setRango('') }} />
        </label>
        <Boton variante="secundario" disabled={cargando} onClick={() => consultar(tableroId, desde, hasta)}>
          {cargando ? 'Consultando…' : 'Consultar'}
        </Boton>
      </div>

      <Aviso>{error}</Aviso>

      {datos && !datos.hay_datos && (
        <div className="rounded-md bg-amber-50 px-3 py-2 text-sm text-amber-900 ring-1 ring-amber-200" role="status">
          No hay mediciones de este tablero entre esas fechas. Pruebe con otro rango.
        </div>
      )}

      {datos?.hay_datos && (
        // Mientras recarga, se mantiene el gráfico anterior atenuado (sin saltos).
        <div className={`space-y-4 transition-opacity ${cargando ? 'opacity-50' : ''}`}>
          <div className="rounded-lg bg-white p-4 shadow-sm ring-1 ring-slate-200">
            <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
              <div className="flex gap-1" role="tablist">
                {Object.entries(VARIABLES).map(([clave, v]) => (
                  <Boton key={clave} role="tab" aria-selected={variable === clave}
                    variante={variable === clave ? 'primario' : 'secundario'} onClick={() => setVariable(clave)}>
                    {v.texto} ({v.unidad})
                  </Boton>
                ))}
              </div>
              {/* Leyenda: siempre presente con 2 o más series */}
              <ul className="flex flex-wrap gap-3 text-xs text-slate-600">
                {series.map((s) => (
                  <li key={s.id} className="flex items-center gap-1.5">
                    <span className="inline-block h-0.5 w-4 rounded" style={{ background: s.color }} />{s.nombre}
                  </li>
                ))}
              </ul>
            </div>
            <GraficoLineas series={series} unidad={def.unidad} hueco={datos.intervalo_segundos * 2000} formatoHora={formatoHora} />
            <p className="mt-2 text-xs text-slate-500">
              Cada punto = promedio de {datos.intervalo_segundos / 60} min.
              {variable === 'corriente' && ' En circuitos trifásicos se muestra la fase más cargada.'}
              {variable === 'voltaje' && ' En circuitos trifásicos se muestra el promedio de las fases.'}
            </p>
          </div>

          {/* Resumen del período (también sirve como vista en tabla de los valores clave) */}
          <div className="overflow-x-auto rounded-lg bg-white shadow-sm ring-1 ring-slate-200">
            <table className="min-w-full divide-y divide-slate-200 text-sm">
              <caption className="px-4 pt-3 text-left text-sm font-semibold text-slate-900">Resumen del período</caption>
              <thead className="bg-slate-50 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">
                <tr>
                  <th className="px-4 py-3">Circuito</th>
                  <th className="px-4 py-3 text-right">Corriente máx. (A)</th>
                  <th className="px-4 py-3 text-right">Potencia máx. (kW)</th>
                  <th className="px-4 py-3 text-right">Energía (kWh)</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {datos.circuitos.map((c, i) => (
                  <tr key={c.id}>
                    <td className="px-4 py-3">
                      <span className="mr-2 inline-block h-0.5 w-4 rounded align-middle" style={{ background: series[i].color }} />
                      <strong>{c.codigo}</strong> <span className="text-slate-500">{c.nombre}</span>
                    </td>
                    <td className="px-4 py-3 text-right tabular-nums">{numero(c.resumen.corriente_max)}</td>
                    <td className="px-4 py-3 text-right tabular-nums">
                      {numero(c.resumen.potencia_max == null ? null : c.resumen.potencia_max / 1000)}
                    </td>
                    <td className="px-4 py-3 text-right tabular-nums">{numero(c.resumen.energia_kwh, 1)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </section>
  )
}
