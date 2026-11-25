// Componentes visuales reutilizables (botones, campos, avisos).
import { useEffect, useRef, useState } from 'react'

const estilosBoton = {
  primario: 'bg-amber-500 text-slate-900 hover:bg-amber-400',
  secundario: 'bg-white text-slate-700 ring-1 ring-slate-300 hover:bg-slate-50',
  peligro: 'bg-white text-red-700 ring-1 ring-red-200 hover:bg-red-50',
  exito: 'bg-white text-emerald-700 ring-1 ring-emerald-200 hover:bg-emerald-50',
}

export function Boton({ variante = 'primario', className = '', ...props }) {
  return (
    <button
      className={`rounded-md px-3 py-1.5 text-sm font-medium transition disabled:cursor-not-allowed disabled:opacity-50 ${estilosBoton[variante]} ${className}`}
      {...props}
    />
  )
}

export function Aviso({ tipo = 'error', children }) {
  if (!children) return null
  const estilo =
    tipo === 'error'
      ? 'bg-red-50 text-red-800 ring-red-200'
      : 'bg-emerald-50 text-emerald-800 ring-emerald-200'
  return <div className={`rounded-md px-3 py-2 text-sm ring-1 ${estilo}`} role="alert">{children}</div>
}

export function Insignia({ activo }) {
  return activo ? (
    <span className="rounded-full bg-emerald-100 px-2 py-0.5 text-xs font-medium text-emerald-800">Activo</span>
  ) : (
    <span className="rounded-full bg-slate-200 px-2 py-0.5 text-xs font-medium text-slate-600">Inactivo</span>
  )
}

const claseInput =
  'mt-1 block w-full rounded-md border border-slate-300 bg-white px-3 py-1.5 text-sm shadow-sm focus:border-amber-500 focus:outline-none focus:ring-1 focus:ring-amber-500'

// Tipo de <input> HTML según el tipo de campo (texto por defecto).
const TIPOS_INPUT = { password: 'password', numero: 'number', fecha: 'date' }

// Campo de formulario según su tipo: texto, numero, fecha, password, select o checkbox.
export function Campo({ campo, valor, onChange, opciones = [] }) {
  const id = `campo-${campo.nombre}`
  if (campo.tipo === 'checkbox') {
    return (
      <div className="flex items-center gap-2 text-sm">
        <input id={id} type="checkbox" checked={Boolean(valor)} onChange={(e) => onChange(e.target.checked)} />
        <label htmlFor={id}>{campo.etiqueta}</label>
      </div>
    )
  }
  return (
    <div>
      <label htmlFor={id} className="block text-sm font-medium text-slate-700">
        {campo.etiqueta}
        {campo.requerido && <span className="text-red-600" aria-hidden="true"> *</span>}
      </label>
      {campo.tipo === 'select' ? (
        <select id={id} className={claseInput} value={valor ?? ''} required={campo.requerido}
          onChange={(e) => onChange(e.target.value)}>
          <option value="">Seleccionar…</option>
          {opciones.map((o) => <option key={o.valor} value={o.valor}>{o.etiqueta}</option>)}
        </select>
      ) : (
        <input id={id} className={claseInput} value={valor ?? ''} required={campo.requerido}
          type={TIPOS_INPUT[campo.tipo] ?? 'text'}
          step={campo.tipo === 'numero' ? 'any' : undefined}
          minLength={campo.minimo} maxLength={campo.maximo}
          autoComplete={campo.tipo === 'password' ? 'new-password' : 'off'}
          onChange={(e) => onChange(e.target.value)} />
      )}
      {campo.ayuda && <p className="mt-1 text-xs text-slate-500">{campo.ayuda}</p>}
    </div>
  )
}

// Muestra la clave de ingesta de un equipo UNA sola vez, con botón para copiarla.
// Al cerrar el aviso, la clave desaparece de la pantalla y no se puede volver a ver.
export function ClaveIngesta({ dispositivo, onCerrar }) {
  const [copiada, setCopiada] = useState(false)
  const caja = useRef(null)

  // Lleva la pantalla hasta el aviso (por si se pidió desde una fila de más abajo).
  useEffect(() => { caja.current?.scrollIntoView({ behavior: 'smooth', block: 'center' }) }, [dispositivo])

  async function copiar() {
    await navigator.clipboard.writeText(dispositivo.clave_ingesta)
    setCopiada(true)
  }

  return (
    <div ref={caja} className="space-y-3 rounded-lg bg-amber-50 p-5 ring-1 ring-amber-300" role="alert">
      <h2 className="font-semibold text-amber-900">
        Clave de ingesta del equipo #{dispositivo.id} ({dispositivo.numero_serie ?? 'sin n.º de serie'})
      </h2>
      <p className="text-sm text-amber-900">
        Cópiala ahora y guárdala en un lugar seguro. <strong>No se volverá a mostrar</strong>.
        No la compartas en capturas ni chats. Si se pierde o se filtra, usa “Regenerar clave”.
      </p>
      <code className="block break-all rounded-md bg-white px-3 py-2 font-mono text-sm ring-1 ring-amber-200">
        {dispositivo.clave_ingesta}
      </code>
      <div className="flex gap-2">
        <Boton onClick={copiar}>{copiada ? 'Copiada ✓' : 'Copiar clave'}</Boton>
        <Boton variante="secundario" onClick={onCerrar}>Ya la guardé, cerrar</Boton>
      </div>
    </div>
  )
}