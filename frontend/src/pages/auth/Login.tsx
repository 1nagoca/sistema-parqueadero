import { useState, type FormEvent } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";

import Button from "@/components/common/Button";
import PasswordInput from "@/components/common/PasswordInput";
import { useAuth } from "@/context/AuthContext";
import { ApiError } from "@/services/api/client";
import { rutaInicioPara } from "@/utils/rutas";

// Pantalla de inicio de sesion.
export default function Login() {
  const { iniciarSesion } = useAuth();
  const navigate = useNavigate();
  // Llega con ?sesion=vencida cuando el token dejo de servir (client.ts).
  const [parametros] = useSearchParams();
  const sesionVencida = parametros.get("sesion") === "vencida";
  // Llega con ?registro=fuera-de-horario si la cuenta se creo con el parqueadero cerrado (Registro.tsx).
  const registroFueraDeHorario = parametros.get("registro") === "fuera-de-horario";
  const [correo, setCorreo] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [enviando, setEnviando] = useState(false);

  // Inicia sesion y lleva al panel segun el rol.
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
        {sesionVencida && (
          <p role="status" className="rounded-lg bg-amber-50 p-3 text-sm text-amber-800">
            Tu sesión terminó. Si eres estudiante, recuerda que el parqueadero funciona de 05:45 a 22:00.
          </p>
        )}
        {registroFueraDeHorario && (
          <p role="status" className="rounded-lg bg-emerald-50 p-3 text-sm text-emerald-800">
            Tu cuenta quedó creada. Podrás iniciar sesión desde las 05:45; el parqueadero funciona de 05:45 a 22:00.
          </p>
        )}
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
          <PasswordInput id="password" required value={password} onChange={(evento) => setPassword(evento.target.value)} />
        </div>

        {error && <p className="text-sm text-red-600">{error}</p>}

        <Button type="submit" className="w-full" disabled={enviando}>
          {enviando ? "Ingresando..." : "Ingresar"}
        </Button>
        <p className="text-center text-sm text-gray-500">
          ¿Eres estudiante y no tienes cuenta?{" "}
          <Link to="/registro" className="text-emerald-700 underline">
            Regístrate
          </Link>
        </p>
      </form>
    </div>
  );
}
