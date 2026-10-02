import { useAuth, puedeEditar } from '../auth.jsx'

const DESCRIPCION_ROL = {
  vsc: 'Como administrador VSC tienes acceso total: puedes crear, editar y desactivar empresas, clientes, sucursales, tableros y usuarios.',
  empresa: 'Ves únicamente la información de tu empresa y de sus clientes.',
  cliente: 'Ves únicamente las sucursales y tableros de tu organización.',
}

export default function Inicio() {
  const { usuario } = useAuth()
  return (
    <section className="max-w-3xl space-y-4">
      <h1 className="text-2xl font-bold text-slate-900">Hola, {usuario.nombre_usuario}</h1>
      <div className="rounded-lg bg-white p-5 shadow-sm ring-1 ring-slate-200">
        <p className="text-sm text-slate-700">{DESCRIPCION_ROL[usuario.rol]}</p>
        <p className="mt-3 text-sm">
          Permiso de edición:{' '}
          <strong className={puedeEditar(usuario) ? 'text-emerald-700' : 'text-slate-500'}>
            {puedeEditar(usuario) ? 'Sí' : 'No (solo lectura)'}
          </strong>
        </p>
      </div>
    </section>
  )
}
