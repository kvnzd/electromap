// Gráfico de líneas en SVG (sin librerías): una línea por serie, eje de tiempo,
// línea vertical que sigue al puntero (o a las flechas del teclado) y un recuadro
// con el valor de TODAS las series en ese momento.
// Cada serie trae su color (lo decide la página que usa el gráfico).
import { useEffect, useMemo, useRef, useState } from 'react'

const ALTO = 300
const MARGEN = { arriba: 24, derecha: 96, abajo: 30, izquierda: 52 }

// Escala "redonda" para el eje Y: 4–6 marcas en números fáciles de leer (1, 2, 5 × 10^n).
function marcasY(min, max) {
  if (min === max) { min -= 1; max += 1 }
  const paso0 = (max - min) / 5
  const base = 10 ** Math.floor(Math.log10(paso0))
  const paso = [1, 2, 5, 10].map((m) => m * base).find((p) => p >= paso0)
  const inicio = Math.floor(min / paso) * paso
  const fin = Math.ceil(max / paso) * paso
  const marcas = []
  for (let v = inicio; v <= fin + paso / 2; v += paso) marcas.push(Number(v.toFixed(6)))
  return marcas
}

// Punto de la serie más cercano al tiempo t (búsqueda binaria; los puntos vienen ordenados).
function masCercano(puntos, t) {
  let bajo = 0, alto = puntos.length - 1
  while (alto - bajo > 1) {
    const medio = (bajo + alto) >> 1
    if (puntos[medio].t < t) bajo = medio; else alto = medio
  }
  return Math.abs(puntos[bajo].t - t) <= Math.abs(puntos[alto].t - t) ? puntos[bajo] : puntos[alto]
}

/**
 * series: [{ id, nombre, color, puntos: [{ t: milisegundos, v: número | null }] }]
 * unidad: texto del eje Y (ej. "A"); hueco: ms sin datos a partir de los cuales la línea se corta.
 */
export default function GraficoLineas({ series, unidad, hueco, formatoHora }) {
  const contenedor = useRef(null)
  const [ancho, setAncho] = useState(700)
  const [cursor, setCursor] = useState(null) // tiempo (ms) señalado por el puntero/teclado

  // El gráfico ocupa todo el ancho disponible y se adapta si cambia la ventana.
  useEffect(() => {
    const observador = new ResizeObserver(([e]) => setAncho(Math.max(320, e.contentRect.width)))
    observador.observe(contenedor.current)
    return () => observador.disconnect()
  }, [])

  const datos = useMemo(() => {
    const todos = series.flatMap((s) => s.puntos.filter((p) => p.v != null))
    if (todos.length === 0) return null
    const tMin = Math.min(...todos.map((p) => p.t)), tMax = Math.max(...todos.map((p) => p.t))
    const marcas = marcasY(Math.min(...todos.map((p) => p.v)), Math.max(...todos.map((p) => p.v)))
    const anchoUtil = ancho - MARGEN.izquierda - MARGEN.derecha
    const altoUtil = ALTO - MARGEN.arriba - MARGEN.abajo
    const x = (t) => MARGEN.izquierda + ((t - tMin) / (tMax - tMin || 1)) * anchoUtil
    const y = (v) => MARGEN.arriba + (1 - (v - marcas[0]) / (marcas.at(-1) - marcas[0])) * altoUtil
    // Ruta SVG de cada serie; se corta ("M") donde faltan datos por más de `hueco`.
    const rutas = series.map((s) => {
      let d = '', anterior = null
      for (const p of s.puntos) {
        if (p.v == null) { anterior = null; continue }
        const cortar = !anterior || p.t - anterior.t > hueco
        d += `${cortar ? 'M' : 'L'}${x(p.t).toFixed(1)},${y(p.v).toFixed(1)}`
        anterior = p
      }
      return d
    })
    const tiempos = Array.from({ length: 6 }, (_, i) => tMin + ((tMax - tMin) * i) / 5)
    return { tMin, tMax, marcas, x, y, rutas, tiempos }
  }, [series, ancho, hueco])

  if (!datos) return <div ref={contenedor} />
  const { tMin, tMax, marcas, x, y, rutas, tiempos } = datos

  function moverA(clientX) {
    const caja = contenedor.current.getBoundingClientRect()
    const t = tMin + ((clientX - caja.left - MARGEN.izquierda) / (ancho - MARGEN.izquierda - MARGEN.derecha)) * (tMax - tMin)
    setCursor(Math.min(tMax, Math.max(tMin, t)))
  }
  function teclado(e) {
    const paso = (tMax - tMin) / 100
    if (e.key === 'ArrowRight') setCursor((c) => Math.min(tMax, (c ?? tMin) + paso))
    else if (e.key === 'ArrowLeft') setCursor((c) => Math.max(tMin, (c ?? tMax) - paso))
    else if (e.key === 'Escape') setCursor(null)
    else return
    e.preventDefault()
  }

  const lectura = cursor == null ? null : series.map((s) => {
    const validos = s.puntos.filter((p) => p.v != null)
    return { serie: s, punto: validos.length ? masCercano(validos, cursor) : null }
  })
  const tLectura = lectura?.find((l) => l.punto)?.punto.t
  const ultimo = (s) => [...s.puntos].reverse().find((p) => p.v != null)

  return (
    <div ref={contenedor} className="relative">
      <svg width={ancho} height={ALTO} role="img" tabIndex={0}
        aria-label={`Gráfico de ${series.map((s) => s.nombre).join(', ')} en ${unidad}. Use las flechas para recorrerlo.`}
        className="rounded focus:outline-none focus-visible:ring-2 focus-visible:ring-amber-500"
        onPointerMove={(e) => moverA(e.clientX)} onPointerLeave={() => setCursor(null)}
        onKeyDown={teclado} onBlur={() => setCursor(null)}>
        {/* Cuadrícula y eje Y (recesivos) */}
        {marcas.map((m) => (
          <g key={m}>
            <line x1={MARGEN.izquierda} x2={ancho - MARGEN.derecha} y1={y(m)} y2={y(m)} stroke="#e2e8f0" strokeWidth="1" />
            <text x={MARGEN.izquierda - 8} y={y(m)} dy="0.32em" textAnchor="end" className="fill-slate-500 text-[11px]">{m}</text>
          </g>
        ))}
        <text x={MARGEN.izquierda - 8} y={10} textAnchor="end" className="fill-slate-500 text-[11px] font-medium">{unidad}</text>
        {/* Eje de tiempo */}
        {tiempos.map((t, i) => (
          <text key={t} x={x(t)} y={ALTO - 8} className="fill-slate-500 text-[11px]"
            textAnchor={i === 0 ? 'start' : i === tiempos.length - 1 ? 'end' : 'middle'}>{formatoHora(t)}</text>
        ))}
        {/* Líneas (2 px) */}
        {series.map((s, i) => (
          <path key={s.id} d={rutas[i]} fill="none" stroke={s.color} strokeWidth="2" strokeLinejoin="round" strokeLinecap="round" />
        ))}
        {/* Etiqueta directa al final de cada línea (texto en color neutro; el color lo lleva la marca) */}
        {series.length <= 4 && series.map((s) => {
          const p = ultimo(s)
          return p && (
            <g key={s.id}>
              <circle cx={x(p.t)} cy={y(p.v)} r="4" fill={s.color} stroke="#fff" strokeWidth="2" />
              <text x={x(p.t) + 8} y={y(p.v)} dy="0.32em" className="fill-slate-700 text-[11px] font-medium">{s.nombre}</text>
            </g>
          )
        })}
        {/* Línea vertical que sigue al puntero + punto en cada serie */}
        {tLectura != null && (
          <g pointerEvents="none">
            <line x1={x(tLectura)} x2={x(tLectura)} y1={MARGEN.arriba} y2={ALTO - MARGEN.abajo} stroke="#94a3b8" strokeWidth="1" />
            {lectura.map(({ serie, punto }) => punto && (
              <circle key={serie.id} cx={x(punto.t)} cy={y(punto.v)} r="4" fill={serie.color} stroke="#fff" strokeWidth="2" />
            ))}
          </g>
        )}
      </svg>

      {/* Recuadro con los valores de todas las series en ese momento */}
      {tLectura != null && (
        <div className="pointer-events-none absolute top-2 z-10 min-w-40 rounded-md bg-white px-3 py-2 text-xs shadow-md ring-1 ring-slate-200"
          style={x(tLectura) > ancho / 2 ? { right: ancho - x(tLectura) + 12 } : { left: x(tLectura) + 12 }}>
          <p className="mb-1 text-slate-500">{formatoHora(tLectura, true)}</p>
          {lectura.map(({ serie, punto }) => (
            <p key={serie.id} className="flex items-center gap-2">
              <span className="inline-block h-0.5 w-3 rounded" style={{ background: serie.color }} />
              <strong className="text-slate-900">{punto ? `${punto.v.toFixed(2)} ${unidad}` : '—'}</strong>
              <span className="text-slate-500">{serie.nombre}</span>
            </p>
          ))}
        </div>
      )}
    </div>
  )
}
