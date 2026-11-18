import { useContext } from "react";

import { AuthContext, type AuthContextValue } from "@/context/contextoAuth";

// Hook para leer la sesion desde cualquier pagina.
export function useAuth(): AuthContextValue {
  const contexto = useContext(AuthContext);
  if (!contexto) {
    throw new Error("useAuth debe usarse dentro de un AuthProvider");
  }
  return contexto;
}
