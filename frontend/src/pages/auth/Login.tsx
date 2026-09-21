import { useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";

import Button from "@/components/common/Button";
import { useAuth } from "@/context/AuthContext";
import { ApiError } from "@/services/api/client";
import { rutaInicioPara } from "@/utils/rutas";

export default function Login() {
  const { iniciarSesion } = useAuth();
  const navigate = useNavigate();
  const [correo, setCorreo] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [enviando, setEnviando] = useState(false);

  async function manejarSubmit(evento: FormEvent) {
    evento.preventDefault();
    setError(null);
    setEnviando(true);
    try {
      const usuarioActual = await iniciarSesion(correo, password);
      navigate(rutaInicioPara(usuarioActual.rol));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "No se pudo iniciar sesion");
    } finally {
      setEnviando(false);
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-gray-50 p-4">
      <form onSubmit={manejarSubmit} className="w-full max-w-sm space-y-4 rounded-2xl bg-white p-6 shadow-sm">
        <h1 className="text-xl font-semibold text-gray-900">Parqueadero</h1>
        <p className="text-sm text-gray-500">Inicia sesion con tu correo institucional.</p>

        <div className="space-y-1">
          <label className="text-sm font-medium text-gray-700" htmlFor="correo">
            Correo institucional
          </label>
          <input
            id="correo"
            type="email"
            required
            value={correo}
            onChange={(evento) => setCorreo(evento.target.value)}
            className="min-h-12 w-full rounded-lg border border-gray-300 px-3 focus:border-emerald-500 focus:outline-none"
          />
        </div>

        <div className="space-y-1">
          <label className="text-sm font-medium text-gray-700" htmlFor="password">
            Contraseña
          </label>
          <input
            id="password"
            type="password"
            required
            value={password}
            onChange={(evento) => setPassword(evento.target.value)}
            className="min-h-12 w-full rounded-lg border border-gray-300 px-3 focus:border-emerald-500 focus:outline-none"
          />
        </div>

        {error && <p className="text-sm text-red-600">{error}</p>}

        <Button type="submit" className="w-full" disabled={enviando}>
          {enviando ? "Ingresando..." : "Ingresar"}
        </Button>
      </form>
    </div>
  );
}
