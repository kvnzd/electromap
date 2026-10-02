// Pantalla genérica de administración: listado + crear + editar + activar/desactivar.
// Cada página (Empresas, Clientes, ...) solo le entrega su configuración.
// OJO: ocultar botones es solo comodidad visual. Quien decide los permisos es el backend.
import { useEffect, useState } from 'react'
import { api } from '../api.js'
import { useAuth } from '../auth.jsx'
import { Aviso, Boton, Campo, Insignia } from './ui.jsx'

function valoresIniciales(campos, fila) {
  const v = {}
  for (const c of campos) v[c.nombre] = fila ? fila[c.nombre] ?? '' : c.defecto ?? (c.tipo === 'checkbox' ? false : '')
  return v
}

// Convierte el formulario en el JSON que espera la API (quita vacíos, convierte números).
function aPayload(campos, valores, usuario, soloCambios = null) {
  const datos = {}
  for (const c of campos) {
    if (c.visible && !c.visible(valores, usuario)) continue
    let v = valores[c.nombre]
    if (c.tipo === 'checkbox') v = Boolean(v)
    else if (v === '' || v === null || v === undefined) {
      if (soloCambios && c.tipo !== 'password' && soloCambios[c.nombre] != null) datos[c.nombre] = null
      continue
    } else if (c.tipo === 'numero' || c.entero) v = Number(v)
    if (soloCambios && soloCambios[c.nombre] === v) continue
    datos[c.nombre] = v
  }
  return datos
}

async function obtenerDatos(ruta, mostrarInactivos, relaciones) {
  const datos = await api(`${ruta}?incluir_inactivos=${mostrarInactivos}`)
  const cargadas = {}
  for (const [nombre, rutaRel] of Object.entries(relaciones)) {
    cargadas[nombre] = await api(`${rutaRel}?incluir_inactivos=true`)
  }
  return [datos, cargadas]
}

export default function PaginaCrud({
  titulo, descripcion, ruta, columnas, camposCrear = [], camposEditar = [],
  relaciones = {}, puedeCrear = () => false, puedeModificar = () => false,
  puedeDesactivar = () => true,
}) {
  const { usuario } = useAuth()
  const [filas, setFilas] = useState([])
  const [rel, setRel] = useState({})
  const [mostrarInactivos, setMostrarInactivos] = useState(false)
  const [formulario, setFormulario] = useState(null) // null | {modo:'crear'} | {modo:'editar', fila}
  const [valores, setValores] = useState({})
  const [error, setError] = useState('')
  const [mensaje, setMensaje] = useState('')
  const [ocupado, setOcupado] = useState(false)

  const [recarga, setRecarga] = useState(0)
  const recargar = () => setRecarga((n) => n + 1)

  // Carga el listado (y las tablas relacionadas, para mostrar nombres en vez de ids).
  const relacionesJson = JSON.stringify(relaciones)
  useEffect(() => {
    let cancelado = false
    obtenerDatos(ruta, mostrarInactivos, JSON.parse(relacionesJson))
      .then(([datos, cargadas]) => {
        if (!cancelado) { setFilas(datos); setRel(cargadas) }
      })
      .catch((e) => { if (!cancelado) setError(e.message) })
    return () => { cancelado = true }
  }, [ruta, mostrarInactivos, relacionesJson, recarga])

  const editable = puedeModificar(usuario)
  const camposActivos = formulario?.modo === 'editar' ? camposEditar : camposCrear

  function abrir(modo, fila = null) {
    setMensaje(''); setError('')
    setFormulario({ modo, fila })
    setValores(valoresIniciales(modo === 'editar' ? camposEditar : camposCrear, fila))
  }

  async function guardar(e) {
    e.preventDefault()
    setOcupado(true); setError(''); setMensaje('')
    try {
      if (formulario.modo === 'crear') {
        await api(ruta, { metodo: 'POST', datos: aPayload(camposCrear, valores, usuario) })
        setMensaje('Registro creado correctamente.')
      } else {
        const datos = aPayload(camposEditar, valores, usuario, formulario.fila)
        await api(`${ruta}/${formulario.fila.id}`, { metodo: 'PATCH', datos })
        setMensaje('Cambios guardados.')
      }
      setFormulario(null)
      recargar()
    } catch (err) {
      setError(err.message)
    } finally {
      setOcupado(false)
    }
  }

  async function cambiarEstado(fila) {
    const accion = fila.activo ? 'desactivar' : 'reactivar'
    if (fila.activo && !window.confirm(`¿Seguro que quieres desactivar este registro?`)) return
    setError(''); setMensaje('')
    try {
      await api(`${ruta}/${fila.id}`, { metodo: 'PATCH', datos: { activo: !fila.activo } })
      setMensaje(`Registro ${accion === 'desactivar' ? 'desactivado' : 'reactivado'}.`)
      recargar()
    } catch (err) {
      setError(err.message)
    }
  }

  return (
    <section className="max-w-6xl space-y-4">
      <header className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">{titulo}</h1>
          {descripcion && <p className="mt-1 text-sm text-slate-500">{descripcion}</p>}
        </div>
        <div className="flex items-center gap-3">
          <label className="flex items-center gap-2 text-sm text-slate-600">
            <input type="checkbox" checked={mostrarInactivos} onChange={(e) => setMostrarInactivos(e.target.checked)} />
            Mostrar inactivos
          </label>
          {puedeCrear(usuario) && camposCrear.length > 0 && (
            <Boton onClick={() => abrir('crear')}>+ Nuevo</Boton>
          )}
        </div>
      </header>

      <Aviso>{error}</Aviso>
      <Aviso tipo="exito">{mensaje}</Aviso>

      {formulario && (
        <form onSubmit={guardar} className="space-y-4 rounded-lg bg-white p-5 shadow-sm ring-1 ring-slate-200">
          <h2 className="font-semibold text-slate-900">
            {formulario.modo === 'crear' ? 'Nuevo registro' : `Editar registro #${formulario.fila.id}`}
          </h2>
          <div className="grid gap-4 sm:grid-cols-2">
            {camposActivos
              .filter((c) => !c.visible || c.visible(valores, usuario))
              .map((c) => (
                <Campo key={c.nombre} campo={c} valor={valores[c.nombre]}
                  opciones={c.opciones ? c.opciones(rel, valores, usuario) : []}
                  onChange={(v) => setValores((prev) => ({ ...prev, [c.nombre]: v }))} />
              ))}
          </div>
          <div className="flex gap-2">
            <Boton type="submit" disabled={ocupado}>{ocupado ? 'Guardando…' : 'Guardar'}</Boton>
            <Boton type="button" variante="secundario" onClick={() => setFormulario(null)}>Cancelar</Boton>
          </div>
        </form>
      )}

      <div className="overflow-hidden rounded-lg bg-white shadow-sm ring-1 ring-slate-200">
        <table className="min-w-full divide-y divide-slate-200 text-sm">
          <thead className="bg-slate-50 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">
            <tr>
              <th className="px-4 py-3">ID</th>
              {columnas.map((c) => <th key={c.titulo} className="px-4 py-3">{c.titulo}</th>)}
              <th className="px-4 py-3">Estado</th>
              {editable && <th className="px-4 py-3 text-right">Acciones</th>}
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {filas.length === 0 && (
              <tr><td colSpan={columnas.length + 3} className="px-4 py-6 text-center text-slate-500">Sin registros.</td></tr>
            )}
            {filas.map((fila) => (
              <tr key={fila.id} className={fila.activo ? '' : 'bg-slate-50 text-slate-400'}>
                <td className="px-4 py-3 font-mono text-xs">{fila.id}</td>
                {columnas.map((c) => <td key={c.titulo} className="px-4 py-3">{c.valor(fila, rel) ?? '—'}</td>)}
                <td className="px-4 py-3"><Insignia activo={fila.activo} /></td>
                {editable && (
                  <td className="space-x-2 whitespace-nowrap px-4 py-3 text-right">
                    {camposEditar.length > 0 && (
                      <Boton variante="secundario" onClick={() => abrir('editar', fila)}>Editar</Boton>
                    )}
                    {puedeDesactivar(fila, usuario) && (
                      <Boton variante={fila.activo ? 'peligro' : 'exito'} onClick={() => cambiarEstado(fila)}>
                        {fila.activo ? 'Desactivar' : 'Reactivar'}
                      </Boton>
                    )}
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
