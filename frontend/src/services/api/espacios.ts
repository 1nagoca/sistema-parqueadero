// Llamadas a espacios (servicio de parqueadero).
import type { Espacio, EspacioCreatePayload } from "@/types/api";
import { apiGet, apiPost } from "./client";

// Espacios de todas las zonas o de una.
export function listarEspacios(zonaId?: string): Promise<Espacio[]> {
  const query = zonaId ? `?zona_id=${encodeURIComponent(zonaId)}` : "";
  return apiGet<Espacio[]>(`/espacios${query}`);
}

// Crea un espacio (admin).
export function crearEspacio(datos: EspacioCreatePayload): Promise<Espacio> {
  return apiPost<Espacio>("/espacios", datos);
}
