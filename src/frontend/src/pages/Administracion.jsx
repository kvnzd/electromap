// Configuración de cada pantalla de administración (qué columnas y campos tiene).
import { useState } from 'react'
import { api } from '../api.js'
import PaginaCrud from '../components/PaginaCrud.jsx'
import { Boton, ClaveIngesta } from '../components/ui.jsx'
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
        { titulo: 'RUT', valor: (f) => f.rut , sinCorte: true },
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
        { titulo: 'Código', valor: (f) => f.codigo, sinCorte: true },
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

// ---------- Equipos AcuRev y circuitos (Etapa 10) ----------

// Un tablero se muestra como "código · nombre" (el código se repite entre sucursales).
const etiquetaTablero = (t) => (t ? `${t.codigo} · ${t.nombre}` : null)
const tableroDe = (lista, id) => etiquetaTablero(lista?.find((x) => x.id === id))
const opcionesTableros = (lista) =>
  (lista ?? []).filter((x) => x.activo).map((x) => ({ valor: x.id, etiqueta: etiquetaTablero(x) }))

const etiquetaEquipo = (d) => (d ? `${d.modelo} · ${d.numero_serie ?? 'sin serie'}` : null)
const equipoDe = (lista, id) => etiquetaEquipo(lista?.find((x) => x.id === id))

// Fecha y hora en formato local (Chile) o "Nunca" si el equipo no ha enviado datos.
const fechaHora = (iso) => (iso ? new Date(iso).toLocaleString('es-CL') : 'Nunca')

const camposDispositivo = [
  { nombre: 'modelo', etiqueta: 'Modelo', requerido: true, maximo: 50, defecto: 'AcuRev 2110-mV-WEB2' },
  { nombre: 'numero_serie', etiqueta: 'N.º de serie', maximo: 50, ayuda: 'Está en la etiqueta del equipo (S/N).' },
  { nombre: 'direccion_ip', etiqueta: 'Dirección IP', maximo: 45, ayuda: 'IP del equipo en la red local. Ej: 192.168.1.50' },
  { nombre: 'fecha_instalacion', etiqueta: 'Fecha de instalación', tipo: 'fecha' },
]

export function Dispositivos() {
  // Equipo recién creado o con clave regenerada: su clave se muestra una sola vez.
  const [conClave, setConClave] = useState(null)

  async function regenerar(fila, { recargar, setError, setMensaje }) {
    const aviso = 'La clave actual dejará de funcionar de inmediato y habrá que configurar ' +
      'la nueva en el equipo. ¿Regenerar la clave?'
    if (!window.confirm(aviso)) return
    setError(''); setMensaje('')
    try {
      setConClave(await api(`/dispositivos/${fila.id}/regenerar-clave`, { metodo: 'POST' }))
      recargar()
    } catch (err) {
      setError(err.message)
    }
  }

  return (
    <PaginaCrud
      titulo="Dispositivos"
      descripcion="Equipos AcuRev instalados en cada tablero. Al registrar un equipo se genera su clave de ingesta, que se muestra una sola vez."
      ruta="/dispositivos"
      relaciones={{ tableros: '/tableros' }}
      columnas={[
        { titulo: 'Modelo', valor: (f) => f.modelo },
        { titulo: 'N.º de serie', valor: (f) => f.numero_serie, sinCorte: true },
        { titulo: 'Tablero', valor: (f, r) => tableroDe(r.tableros, f.tablero_id) },
        { titulo: 'IP', valor: (f) => f.direccion_ip, sinCorte: true },
        { titulo: 'Última comunicación', valor: (f) => fechaHora(f.ultima_comunicacion) },
      ]}
      camposCrear={[
        { nombre: 'tablero_id', etiqueta: 'Tablero', tipo: 'select', entero: true, requerido: true,
          opciones: (r) => opcionesTableros(r.tableros) },
        ...camposDispositivo,
      ]}
      // El tablero no se cambia: si el equipo se traslada, se registra uno nuevo (historial limpio).
      camposEditar={camposDispositivo}
      puedeCrear={puedeEditar}
      puedeModificar={puedeEditar}
      alCrear={setConClave}
      accionesFila={(fila, acciones) => fila.activo && (
        <Boton variante="secundario" onClick={() => regenerar(fila, acciones)}>Regenerar clave</Boton>
      )}
    >
      {conClave && <ClaveIngesta dispositivo={conClave} onCerrar={() => setConClave(null)} />}
    </PaginaCrud>
  )
}

// Equipos activos del tablero elegido en el formulario (un circuito solo se conecta a un equipo de su tablero).
const opcionesEquipos = (r, valores) =>
  (r.dispositivos ?? [])
    .filter((d) => d.activo && d.tablero_id === Number(valores.tablero_id))
    .map((d) => ({ valor: d.id, etiqueta: etiquetaEquipo(d) }))

const camposCircuito = [
  { nombre: 'dispositivo_id', etiqueta: 'Equipo AcuRev', tipo: 'select', entero: true,
    opciones: opcionesEquipos, ayuda: 'Solo aparecen los equipos del tablero elegido.' },
  { nombre: 'codigo', etiqueta: 'Código', requerido: true, maximo: 20, ayuda: 'Ej: C1' },
  { nombre: 'nombre', etiqueta: 'Nombre', requerido: true, maximo: 100, ayuda: 'Ej: Alumbrado' },
  { nombre: 'canal_acurev', etiqueta: 'Canal AcuRev', maximo: 30,
    ayuda: 'Identificador del canal en el CSV del equipo. Requiere un equipo asignado.' },
  { nombre: 'calibre_cable_mm2', etiqueta: 'Calibre del cable (mm²)', tipo: 'numero',
    ayuda: 'Debe existir en la tabla de calibres. Déjalo vacío si aún no está cargada.' },
  { nombre: 'corriente_automatico', etiqueta: 'Corriente del automático (A)', tipo: 'numero' },
]

export function Circuitos() {
  return (
    <PaginaCrud
      titulo="Circuitos"
      descripcion="Circuitos de cada tablero y el canal del AcuRev que los mide. El código no se repite dentro de un tablero y el canal no se repite dentro de un equipo."
      ruta="/circuitos"
      relaciones={{ tableros: '/tableros', dispositivos: '/dispositivos' }}
      columnas={[
        { titulo: 'Código', valor: (f) => f.codigo, sinCorte: true },
        { titulo: 'Nombre', valor: (f) => f.nombre },
        { titulo: 'Tablero', valor: (f, r) => tableroDe(r.tableros, f.tablero_id) },
        { titulo: 'Equipo', valor: (f, r) => equipoDe(r.dispositivos, f.dispositivo_id) },
        { titulo: 'Canal', valor: (f) => f.canal_acurev },
        { titulo: 'Calibre', valor: (f) => (f.calibre_cable_mm2 != null ? `${f.calibre_cable_mm2} mm²` : null), sinCorte: true },
        { titulo: 'Automático', valor: (f) => (f.corriente_automatico != null ? `${f.corriente_automatico} A` : null), sinCorte: true },
      ]}
      camposCrear={[
        { nombre: 'tablero_id', etiqueta: 'Tablero', tipo: 'select', entero: true, requerido: true,
          opciones: (r) => opcionesTableros(r.tableros) },
        ...camposCircuito,
      ]}
      // tablero_id va oculto al editar: no se envía, pero sirve para filtrar los equipos del tablero.
      camposEditar={[
        { nombre: 'tablero_id', visible: () => false },
        ...camposCircuito,
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
