// Configuración de cada pantalla de administración (qué columnas y campos tiene).
import PaginaCrud from '../components/PaginaCrud.jsx'
import { puedeEditar } from '../auth.jsx'

const esVsc = (u) => u.rol === 'vsc'
const nombreDe = (lista, id) => lista?.find((x) => x.id === id)?.nombre
const opcionesActivas = (lista) =>
  (lista ?? []).filter((x) => x.activo).map((x) => ({ valor: x.id, etiqueta: x.nombre }))

export function Empresas() {
  return (
    <PaginaCrud
      titulo="Empresas"
      descripcion="Solo el administrador VSC puede crear, editar o desactivar empresas. Desactivar una empresa corta el acceso a todos sus usuarios."
      ruta="/empresas"
      columnas={[
        { titulo: 'Nombre', valor: (f) => f.nombre },
        { titulo: 'RUT', valor: (f) => f.rut },
        { titulo: 'Correo de contacto', valor: (f) => f.contacto_email },
      ]}
      camposCrear={[
        { nombre: 'nombre', etiqueta: 'Nombre', requerido: true, maximo: 150 },
        { nombre: 'rut', etiqueta: 'RUT', maximo: 12, ayuda: 'Ej: 76123456-7' },
        { nombre: 'contacto_email', etiqueta: 'Correo de contacto', maximo: 150 },
      ]}
      camposEditar={[
        { nombre: 'nombre', etiqueta: 'Nombre', requerido: true, maximo: 150 },
        { nombre: 'rut', etiqueta: 'RUT', maximo: 12 },
        { nombre: 'contacto_email', etiqueta: 'Correo de contacto', maximo: 150 },
      ]}
      puedeCrear={esVsc}
      puedeModificar={esVsc}
    />
  )
}

export function Clientes() {
  return (
    <PaginaCrud
      titulo="Clientes"
      descripcion="Clientes finales de cada empresa."
      ruta="/clientes"
      relaciones={{ empresas: '/empresas' }}
      columnas={[
        { titulo: 'Nombre', valor: (f) => f.nombre },
        { titulo: 'Empresa', valor: (f, r) => nombreDe(r.empresas, f.empresa_id) },
      ]}
      camposCrear={[
        { nombre: 'nombre', etiqueta: 'Nombre', requerido: true, maximo: 150 },
        // Solo VSC elige empresa; un usuario empresa crea siempre en la suya (lo asigna el backend).
        { nombre: 'empresa_id', etiqueta: 'Empresa', tipo: 'select', entero: true, requerido: true,
          opciones: (r) => opcionesActivas(r.empresas), visible: (_, u) => esVsc(u) },
      ]}
      camposEditar={[{ nombre: 'nombre', etiqueta: 'Nombre', requerido: true, maximo: 150 }]}
      puedeCrear={puedeEditar}
      puedeModificar={puedeEditar}
    />
  )
}

export function Sucursales() {
  return (
    <PaginaCrud
      titulo="Sucursales"
      descripcion="Ubicaciones de cada cliente."
      ruta="/sucursales"
      relaciones={{ clientes: '/clientes' }}
      columnas={[
        { titulo: 'Nombre', valor: (f) => f.nombre },
        { titulo: 'Cliente', valor: (f, r) => nombreDe(r.clientes, f.cliente_id) },
        { titulo: 'Dirección', valor: (f) => f.direccion },
      ]}
      camposCrear={[
        { nombre: 'cliente_id', etiqueta: 'Cliente', tipo: 'select', entero: true, requerido: true,
          opciones: (r) => opcionesActivas(r.clientes) },
        { nombre: 'nombre', etiqueta: 'Nombre', requerido: true, maximo: 100 },
        { nombre: 'direccion', etiqueta: 'Dirección', maximo: 200 },
      ]}
      camposEditar={[
        { nombre: 'nombre', etiqueta: 'Nombre', requerido: true, maximo: 100 },
        { nombre: 'direccion', etiqueta: 'Dirección', maximo: 200 },
      ]}
      puedeCrear={puedeEditar}
      puedeModificar={puedeEditar}
    />
  )
}

export function Tableros() {
  return (
    <PaginaCrud
      titulo="Tableros"
      descripcion="Tableros eléctricos de cada sucursal. El código no se puede repetir dentro de una sucursal."
      ruta="/tableros"
      relaciones={{ sucursales: '/sucursales' }}
      columnas={[
        { titulo: 'Código', valor: (f) => f.codigo },
        { titulo: 'Nombre', valor: (f) => f.nombre },
        { titulo: 'Sucursal', valor: (f, r) => nombreDe(r.sucursales, f.sucursal_id) },
        { titulo: 'Ubicación', valor: (f) => f.ubicacion },
        { titulo: 'Amperaje nominal', valor: (f) => (f.amperaje_nominal != null ? `${f.amperaje_nominal} A` : null) },
      ]}
      camposCrear={[
        { nombre: 'sucursal_id', etiqueta: 'Sucursal', tipo: 'select', entero: true, requerido: true,
          opciones: (r) => opcionesActivas(r.sucursales) },
        { nombre: 'codigo', etiqueta: 'Código', requerido: true, maximo: 20, ayuda: 'Ej: TG-01' },
        { nombre: 'nombre', etiqueta: 'Nombre', requerido: true, maximo: 100 },
        { nombre: 'ubicacion', etiqueta: 'Ubicación', maximo: 200 },
        { nombre: 'amperaje_nominal', etiqueta: 'Amperaje nominal (A)', tipo: 'numero' },
      ]}
      camposEditar={[
        { nombre: 'codigo', etiqueta: 'Código', requerido: true, maximo: 20 },
        { nombre: 'nombre', etiqueta: 'Nombre', requerido: true, maximo: 100 },
        { nombre: 'ubicacion', etiqueta: 'Ubicación', maximo: 200 },
        { nombre: 'amperaje_nominal', etiqueta: 'Amperaje nominal (A)', tipo: 'numero' },
      ]}
      puedeCrear={puedeEditar}
      puedeModificar={puedeEditar}
    />
  )
}

const ROLES = { vsc: 'Administrador VSC', empresa: 'Empresa', cliente: 'Cliente final' }

export function Usuarios() {
  return (
    <PaginaCrud
      titulo="Usuarios"
      descripcion="El nivel de acceso (rol y empresa/cliente) se fija al crear el usuario y no se cambia después. Un cliente nunca puede editar."
      ruta="/usuarios"
      relaciones={{ empresas: '/empresas', clientes: '/clientes' }}
      columnas={[
        { titulo: 'Usuario', valor: (f) => f.nombre_usuario },
        { titulo: 'Rol', valor: (f) => ROLES[f.rol] },
        { titulo: 'Pertenece a', valor: (f, r) =>
            f.empresa_id ? nombreDe(r.empresas, f.empresa_id) : f.cliente_id ? nombreDe(r.clientes, f.cliente_id) : 'Plataforma' },
        { titulo: 'Puede editar', valor: (f) => (f.puede_editar ? 'Sí' : 'No') },
      ]}
      camposCrear={[
        { nombre: 'nombre_usuario', etiqueta: 'Nombre de usuario', requerido: true, minimo: 3, maximo: 50 },
        { nombre: 'password', etiqueta: 'Contraseña', tipo: 'password', requerido: true, minimo: 10,
          ayuda: 'Mínimo 10 caracteres.' },
        { nombre: 'rol', etiqueta: 'Rol', tipo: 'select', requerido: true,
          opciones: (_, __, u) =>
            (u.rol === 'vsc' ? ['vsc', 'empresa', 'cliente'] : ['empresa', 'cliente'])
              .map((r) => ({ valor: r, etiqueta: ROLES[r] })) },
        { nombre: 'empresa_id', etiqueta: 'Empresa', tipo: 'select', entero: true, requerido: true,
          opciones: (r) => opcionesActivas(r.empresas),
          visible: (v, u) => v.rol === 'empresa' && esVsc(u) },
        { nombre: 'cliente_id', etiqueta: 'Cliente', tipo: 'select', entero: true, requerido: true,
          opciones: (r) => opcionesActivas(r.clientes), visible: (v) => v.rol === 'cliente' },
        { nombre: 'puede_editar', etiqueta: 'Puede editar', tipo: 'checkbox',
          visible: (v) => v.rol === 'empresa' },
      ]}
      camposEditar={[
        { nombre: 'puede_editar', etiqueta: 'Puede editar (solo usuarios empresa)', tipo: 'checkbox' },
        { nombre: 'password', etiqueta: 'Nueva contraseña (opcional)', tipo: 'password', minimo: 10,
          ayuda: 'Déjala vacía para no cambiarla.' },
      ]}
      puedeCrear={puedeEditar}
      puedeModificar={puedeEditar}
      // Nadie puede desactivar su propia cuenta (el backend también lo impide).
      puedeDesactivar={(fila, u) => fila.id !== u.id}
    />
  )
}
