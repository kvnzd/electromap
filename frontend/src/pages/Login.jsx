import { useState } from 'react'
import { Navigate } from 'react-router-dom'
import { useAuth } from '../auth.jsx'
import { Aviso, Boton } from '../components/ui.jsx'

export default function Login() {
  const { usuario, iniciarSesion } = useAuth()
  const [nombre, setNombre] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [ocupado, setOcupado] = useState(false)

  if (usuario) return <Navigate to="/" replace />

  async function enviar(e) {
    e.preventDefault()
    setOcupado(true); setError('')
    try {
      await iniciarSesion(nombre, password)
    } catch (err) {
      setError(err.message)
    } finally {
      setOcupado(false)
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-slate-900 p-4">
      <form onSubmit={enviar} className="w-full max-w-sm space-y-4 rounded-xl bg-white p-8 shadow-xl">
        <div className="text-center">
          <p className="text-2xl font-bold text-slate-900">Electro<span className="text-amber-500">Map</span></p>
          <p className="text-sm text-slate-500">Monitoreo de tableros eléctricos</p>
        </div>
        <label className="block text-sm font-medium text-slate-700">
          Usuario
          <input className="mt-1 block w-full rounded-md border border-slate-300 px-3 py-2 text-sm focus:border-amber-500 focus:outline-none focus:ring-1 focus:ring-amber-500"
            value={nombre} onChange={(e) => setNombre(e.target.value)} autoComplete="username" required autoFocus />
        </label>
        <label className="block text-sm font-medium text-slate-700">
          Contraseña
          <input type="password" className="mt-1 block w-full rounded-md border border-slate-300 px-3 py-2 text-sm focus:border-amber-500 focus:outline-none focus:ring-1 focus:ring-amber-500"
            value={password} onChange={(e) => setPassword(e.target.value)} autoComplete="current-password" required />
        </label>
        <Aviso>{error}</Aviso>
        <Boton type="submit" disabled={ocupado} className="w-full py-2">
          {ocupado ? 'Ingresando…' : 'Ingresar'}
        </Boton>
      </form>
    </div>
  )
}
