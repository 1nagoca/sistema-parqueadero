import type { Espacio, EspacioCreatePayload } from "@/types/api";
import { apiGet, apiPost } from "./client";

export function listarEspacios(zonaId?: string): Promise<Espacio[]> {
  const query = zonaId ? `?zona_id=${encodeURIComponent(zonaId)}` : "";
  return apiGet<Espacio[]>(`/espacios${query}`);
}

export function crearEspacio(datos: EspacioCreatePayload): Promise<Espacio> {
  return apiPost<Espacio>("/espacios", datos);
}
