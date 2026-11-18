// Sesion del usuario compartida por toda la app (quien esta conectado y su rol).
import { useEffect, useState, type ReactNode } from "react";

import { AuthContext } from "@/context/contextoAuth";
import { login as loginApi } from "@/services/api/auth";
import { borrarToken, guardarToken, obtenerToken } from "@/services/api/client";
import { obtenerUsuarioActual } from "@/services/api/usuarios";
import type { Usuario } from "@/types/api";

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
