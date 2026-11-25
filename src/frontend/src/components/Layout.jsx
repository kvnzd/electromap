// Estructura de la aplicación: menú lateral (según el rol) + contenido.
// En pantallas chicas (celular) el menú se esconde y se abre con el botón ☰ (Etapa 24).
import { useEffect, useState } from 'react'
import { NavLink, Outlet } from 'react-router-dom'
import { useAuth } from '../auth.jsx'

const NOMBRE_ROL = { vsc: 'Administrador VSC', empresa: 'Empresa', cliente: 'Cliente final' }

// Qué secciones ve cada rol en el menú.
function seccionesPara(rol) {
  const s = [{ ruta: '/', texto: 'Inicio' }, { ruta: '/en-vivo', texto: 'En vivo' }, { ruta: '/alarmas', texto: 'Alarmas' }]
  if (rol === 'vsc') s.push({ ruta: '/empresas', texto: 'Empresas' })
  if (rol === 'empresa') s.push({ ruta: '/empresas', texto: 'Mi empresa' })
  if (rol !== 'cliente') s.push({ ruta: '/clientes', texto: 'Clientes' })
  s.push({ ruta: '/sucursales', texto: 'Sucursales' })
  s.push({ ruta: '/tableros', texto: 'Tableros' })
  s.push({ ruta: '/dispositivos', texto: 'Dispositivos' })
  s.push({ ruta: '/circuitos', texto: 'Circuitos' })
  s.push({ ruta: '/umbrales', texto: 'Umbrales' })
  s.push({ ruta: '/historial', texto: 'Historial' })
  if (rol !== 'cliente') s.push({ ruta: '/usuarios', texto: 'Usuarios' })
  return s
}

function Logo() {
  return (
    <>
      <p className="text-lg font-bold text-white">
        Electro<span className="text-amber-400">Map</span>
      </p>
      <p className="text-xs text-slate-400">VSC · VoltSense Cloud</p>
    </>
  )
}

export default function Layout() {
  const { usuario, cerrarSesion } = useAuth()
  const [menuAbierto, setMenuAbierto] = useState(false) // solo importa en celular
  const cerrarMenu = () => setMenuAbierto(false)

  // Con el menú abierto en el celular, la tecla Escape lo cierra.
  useEffect(() => {
    if (!menuAbierto) return
    const alPresionar = (e) => { if (e.key === 'Escape') setMenuAbierto(false) }
    window.addEventListener('keydown', alPresionar)
    return () => window.removeEventListener('keydown', alPresionar)
  }, [menuAbierto])

  return (
    <div className="min-h-screen md:flex">
      {/* Barra superior: solo en celular */}
      <header className="sticky top-0 z-30 flex items-center justify-between bg-slate-900 px-4 py-2 md:hidden">
        <div><Logo /></div>
        <button type="button" onClick={() => setMenuAbierto(true)} aria-label="Abrir menú" aria-expanded={menuAbierto}
          className="rounded-md px-3 py-2 text-xl leading-none text-white hover:bg-slate-800">☰</button>
      </header>

      {/* Fondo oscuro detrás del menú abierto (celular): tocarlo cierra el menú */}
      {menuAbierto && <div className="fixed inset-0 z-40 bg-black/50 md:hidden" onClick={cerrarMenu} aria-hidden="true" />}

      <aside className={`fixed inset-y-0 left-0 z-50 flex w-64 flex-col overflow-y-auto bg-slate-900 text-slate-200 transition-transform
        md:static md:z-auto md:w-56 md:translate-x-0 ${menuAbierto ? 'translate-x-0' : '-translate-x-full'}`}>
        <div className="flex items-start justify-between border-b border-slate-800 px-5 py-4">
          <div><Logo /></div>
          <button type="button" onClick={cerrarMenu} aria-label="Cerrar menú"
            className="rounded-md px-2 text-xl leading-none text-slate-400 hover:text-white md:hidden">✕</button>
        </div>
        <nav className="flex-1 space-y-1 p-3">
          {seccionesPara(usuario.rol).map((s) => (
            <NavLink key={s.ruta} to={s.ruta} end={s.ruta === '/'} onClick={cerrarMenu}
              className={({ isActive }) =>
                `block rounded-md px-3 py-2 text-sm ${isActive ? 'bg-slate-800 font-medium text-amber-400' : 'hover:bg-slate-800'}`
              }>
              {s.texto}
            </NavLink>
          ))}
        </nav>
        <div className="border-t border-slate-800 p-4 text-sm">
          <p className="font-medium text-white">{usuario.nombre_usuario}</p>
          <p className="text-xs text-slate-400">
            {NOMBRE_ROL[usuario.rol]}
            {usuario.rol === 'empresa' && (usuario.puede_editar ? ' · editor' : ' · solo lectura')}
          </p>
          <button onClick={cerrarSesion} className="mt-3 text-xs text-slate-400 underline hover:text-white">
            Cerrar sesión
          </button>
        </div>
      </aside>

      <main className="min-w-0 flex-1 overflow-x-auto p-4 md:p-8">
        <Outlet />
      </main>
    </div>
  )
}