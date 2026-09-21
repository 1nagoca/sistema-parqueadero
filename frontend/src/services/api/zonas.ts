import type { Zona, ZonaCreatePayload } from "@/types/api";
import { apiGet, apiPost } from "./client";

export function listarZonas(): Promise<Zona[]> {
  return apiGet<Zona[]>("/zonas");
}

export function crearZona(datos: ZonaCreatePayload): Promise<Zona> {
  return apiPost<Zona>("/zonas", datos);
}
