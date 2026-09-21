import type { Acceso, AccesoActivo, AccesoEntradaPayload } from "@/types/api";
import { apiGet, apiPost, ApiError } from "./client";

export function listarAccesosActivos(zonaId: string): Promise<AccesoActivo[]> {
  return apiGet<AccesoActivo[]>(`/accesos?zona_id=${encodeURIComponent(zonaId)}`);
}

export async function buscarAccesoActivoPorPlaca(placa: string): Promise<Acceso | null> {
  try {
    return await apiGet<Acceso>(`/accesos/buscar?placa=${encodeURIComponent(placa)}`);
  } catch (error) {
    if (error instanceof ApiError && error.status === 404) {
      return null;
    }
    throw error;
  }
}

export function registrarEntrada(datos: AccesoEntradaPayload): Promise<Acceso> {
  return apiPost<Acceso>("/accesos/entrada", datos);
}

export function registrarSalida(accesoId: string): Promise<Acceso> {
  return apiPost<Acceso>(`/accesos/${accesoId}/salida`);
}
