// Estructura de la aplicación: menú lateral (según el rol) + contenido.
import { NavLink, Outlet } from 'react-router-dom'
import { useAuth } from '../auth.jsx'

const NOMBRE_ROL = { vsc: 'Administrador VSC', empresa: 'Empresa', cliente: 'Cliente final' }

// Qué secciones ve cada rol en el menú.
function seccionesPara(rol) {
  const s = [{ ruta: '/', texto: 'Inicio' }]
  if (rol === 'vsc') s.push({ ruta: '/empresas', texto: 'Empresas' })
  if (rol === 'empresa') s.push({ ruta: '/empresas', texto: 'Mi empresa' })
  if (rol !== 'cliente') s.push({ ruta: '/clientes', texto: 'Clientes' })
  s.push({ ruta: '/sucursales', texto: 'Sucursales' })
  s.push({ ruta: '/tableros', texto: 'Tableros' })
  if (rol !== 'cliente') s.push({ ruta: '/usuarios', texto: 'Usuarios' })
  return s
}

export default function Layout() {
  const { usuario, cerrarSesion } = useAuth()

  return (
    <div className="flex min-h-screen">
      <aside className="flex w-56 flex-col bg-slate-900 text-slate-200">
        <div className="border-b border-slate-800 px-5 py-4">
          <p className="text-lg font-bold text-white">
            Electro<span className="text-amber-400">Map</span>
          </p>
          <p className="text-xs text-slate-400">VSC · VoltSense Cloud</p>
        </div>
        <nav className="flex-1 space-y-1 p-3">
          {seccionesPara(usuario.rol).map((s) => (
            <NavLink key={s.ruta} to={s.ruta} end={s.ruta === '/'}
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
      <main className="flex-1 overflow-x-auto p-8">
        <Outlet />
      </main>
    </div>
  )
}
