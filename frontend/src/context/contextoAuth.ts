// Contexto de la sesion, compartido por AuthProvider y useAuth.
import { createContext } from "react";

import type { Usuario } from "@/types/api";

// Lo que ofrece el contexto a las paginas.
export interface AuthContextValue {
  usuario: Usuario | null;
  cargando: boolean;
  iniciarSesion: (correo: string, password: string) => Promise<Usuario>;
  cerrarSesion: () => void;
}

export const AuthContext = createContext<AuthContextValue | undefined>(undefined);
