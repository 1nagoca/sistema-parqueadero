import { createContext, useContext, useEffect, useState, type ReactNode } from "react";

import { login as loginApi } from "@/services/api/auth";
import { borrarToken, guardarToken, obtenerToken } from "@/services/api/client";
import { obtenerUsuarioActual } from "@/services/api/usuarios";
import type { Usuario } from "@/types/api";

interface AuthContextValue {
  usuario: Usuario | null;
  cargando: boolean;
  iniciarSesion: (correo: string, password: string) => Promise<Usuario>;
  cerrarSesion: () => void;
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [usuario, setUsuario] = useState<Usuario | null>(null);
  const [cargando, setCargando] = useState(true);

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

  async function iniciarSesion(correo: string, password: string): Promise<Usuario> {
    const { access_token: token } = await loginApi(correo, password);
    guardarToken(token);
    const usuarioActual = await obtenerUsuarioActual();
    setUsuario(usuarioActual);
    return usuarioActual;
  }

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

export function useAuth(): AuthContextValue {
  const contexto = useContext(AuthContext);
  if (!contexto) {
    throw new Error("useAuth debe usarse dentro de un AuthProvider");
  }
  return contexto;
}
