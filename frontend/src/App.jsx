// Rutas de la aplicación. Todo lo que no es /login exige sesión iniciada.
import { Navigate, Route, Routes } from 'react-router-dom'
import { useAuth } from './auth.jsx'
import Layout from './components/Layout.jsx'
import {
  Circuitos, Clientes, Dispositivos, Empresas, Sucursales, Tableros, Usuarios,
} from './pages/Administracion.jsx'
import Alarmas from './pages/Alarmas.jsx'
import EnVivo from './pages/EnVivo.jsx'
import Historial from './pages/Historial.jsx'
import Inicio from './pages/Inicio.jsx'
import Login from './pages/Login.jsx'
import Umbrales from './pages/Umbrales.jsx'

function RequiereSesion({ children }) {
  const { usuario, cargando } = useAuth()
  if (cargando) return <p className="p-8 text-slate-500">Cargando…</p>
  if (!usuario) return <Navigate to="/login" replace />
  return children
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route element={<RequiereSesion><Layout /></RequiereSesion>}>
        <Route index element={<Inicio />} />
        <Route path="empresas" element={<Empresas />} />
        <Route path="clientes" element={<Clientes />} />
        <Route path="sucursales" element={<Sucursales />} />
        <Route path="tableros" element={<Tableros />} />
        <Route path="dispositivos" element={<Dispositivos />} />
        <Route path="circuitos" element={<Circuitos />} />
        <Route path="en-vivo" element={<EnVivo />} />
        <Route path="alarmas" element={<Alarmas />} />
        <Route path="umbrales" element={<Umbrales />} />
        <Route path="historial" element={<Historial />} />
        <Route path="usuarios" element={<Usuarios />} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}
