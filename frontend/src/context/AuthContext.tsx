// Sesion del usuario compartida por toda la app (quien esta conectado y su rol).
import { createContext, useContext, useEffect, useState, type ReactNode } from "react";

import { login as loginApi } from "@/services/api/auth";
import { borrarToken, guardarToken, obtenerToken } from "@/services/api/client";
import { obtenerUsuarioActual } from "@/services/api/usuarios";
import type { Usuario } from "@/types/api";

// Lo que ofrece el contexto a las paginas.
interface AuthContextValue {
  usuario: Usuario | null;
  cargando: boolean;
  iniciarSesion: (correo: string, password: string) => Promise<Usuario>;
  cerrarSesion: () => void;
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

// Envuelve la app y guarda el usuario de la sesion.
export function AuthProvider({ children }: { children: ReactNode }) {
  const [usuario, setUsuario] = useState<Usuario | null>(null);
  const [cargando, setCargando] = useState(true);

  // Al abrir la app, si hay token guardado recupera el usuario; si el token ya no sirve, lo borra.
  useEffect(() => {
    if (!obtenerToken()) {
      setCargando(false);
      return;
    }
    obtenerUsuarioActual()
      .then(setUsuario)
      .catch(() => borrarToken())
      .finally(() => setCargando(false));
  }, []);

  // Pide el token, lo guarda y carga el usuario.
  async function iniciarSesion(correo: string, password: string): Promise<Usuario> {
    const { access_token: token } = await loginApi(correo, password);
    guardarToken(token);
    const usuarioActual = await obtenerUsuarioActual();
    setUsuario(usuarioActual);
    return usuarioActual;
  }

  // Borra el token y el usuario.
  function cerrarSesion(): void {
    borrarToken();
    setUsuario(null);
  }

  return (
    <AuthContext.Provider value={{ usuario, cargando, iniciarSesion, cerrarSesion }}>
      {children}
    </AuthContext.Provider>
  );
}

// Hook para leer la sesion desde cualquier pagina.
export function useAuth(): AuthContextValue {
  const contexto = useContext(AuthContext);
  if (!contexto) {
    throw new Error("useAuth debe usarse dentro de un AuthProvider");
  }
  return contexto;
}
