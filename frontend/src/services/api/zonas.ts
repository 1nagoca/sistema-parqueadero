// Llamadas a zonas (servicio de parqueadero).
import type { Zona, ZonaCreatePayload } from "@/types/api";
import { apiGet, apiPost } from "./client";

// Zonas activas con sus cupos.
export function listarZonas(): Promise<Zona[]> {
  return apiGet<Zona[]>("/zonas");
}

// Crea una zona (admin).
export function crearZona(datos: ZonaCreatePayload): Promise<Zona> {
  return apiPost<Zona>("/zonas", datos);
}
