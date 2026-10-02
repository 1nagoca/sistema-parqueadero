import { useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";

import Button from "@/components/common/Button";
import { useAuth } from "@/context/AuthContext";
import { registrarEstudiante } from "@/services/api/auth";
import { ApiError } from "@/services/api/client";
import { rutaInicioPara } from "@/utils/rutas";

const campo = "min-h-12 w-full rounded-lg border border-gray-300 px-3 focus:border-emerald-500 focus:outline-none";

export default function Registro() {
  const { iniciarSesion } = useAuth();
  const navigate = useNavigate();
  const [nombre, setNombre] = useState("");
  const [correo, setCorreo] = useState("");
  const [documento, setDocumento] = useState("");
  const [telefono, setTelefono] = useState("");
  const [password, setPassword] = useState("");
  const [confirmacion, setConfirmacion] = useState("");
  const [acepta, setAcepta] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [enviando, setEnviando] = useState(false);

  async function manejarSubmit(evento: FormEvent) {
    evento.preventDefault();
    setError(null);
    if (password !== confirmacion) {
      setError("Las contraseñas no coinciden");
      return;
    }
    setEnviando(true);
    try {
      await registrarEstudiante({
        nombre_completo: nombre,
        correo_institucional: correo,
        documento_identidad: documento,
        telefono: telefono || null,
        password,
        acepta_tratamiento_datos: acepta,
      });
      // Entra directo a su panel para subir el carnet y registrar su vehiculo.
      const usuarioActual = await iniciarSesion(correo, password);
      navigate(rutaInicioPara(usuarioActual.rol));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "No se pudo completar el registro");
    } finally {
      setEnviando(false);
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-gray-50 p-4">
      <form onSubmit={manejarSubmit} className="w-full max-w-md space-y-4 rounded-2xl bg-white p-6 shadow-sm">
        <h1 className="text-xl font-semibold text-gray-900">Registro de estudiantes</h1>
        <p className="text-sm text-gray-500">
          Universidad Francisco de Paula Santander. Tu contraseña la defines tú: nadie más, ni el administrador,
          puede verla.
        </p>

        <input required placeholder="Nombre completo" value={nombre} onChange={(e) => setNombre(e.target.value)} className={campo} />
        <input
          required
          type="email"
          placeholder="Correo institucional (@ufps.edu.co)"
          value={correo}
          onChange={(e) => setCorreo(e.target.value)}
          className={campo}
        />
        <input
          required
          placeholder="Documento de identidad"
          value={documento}
          onChange={(e) => setDocumento(e.target.value)}
          className={campo}
        />
        <input placeholder="Teléfono (opcional)" value={telefono} onChange={(e) => setTelefono(e.target.value)} className={campo} />
        <input
          required
          type="password"
          minLength={8}
          placeholder="Contraseña (mínimo 8 caracteres)"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          className={campo}
        />
        <input
          required
          type="password"
          placeholder="Confirma la contraseña"
          value={confirmacion}
          onChange={(e) => setConfirmacion(e.target.value)}
          className={campo}
        />

        <label className="flex items-start gap-2 text-sm text-gray-700">
          <input type="checkbox" checked={acepta} onChange={(e) => setAcepta(e.target.checked)} className="mt-1 h-4 w-4" />
          <span>
            Autorizo el tratamiento de mis datos personales y de las imágenes de mi carnet, placa y tarjeta de
            propiedad, únicamente para verificar mi acceso al parqueadero (Ley 1581 de 2012).
          </span>
        </label>

        {error && <p className="text-sm text-red-600">{error}</p>}

        <Button type="submit" className="w-full" disabled={enviando || !acepta}>
          {enviando ? "Registrando..." : "Crear cuenta"}
        </Button>
        <p className="text-center text-sm text-gray-500">
          ¿Ya tienes cuenta?{" "}
          <Link to="/login" className="text-emerald-700 underline">
            Inicia sesión
          </Link>
        </p>
      </form>
    </div>
  );
}
