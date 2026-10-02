import type { SolicitudVerificacion, Usuario, Vehiculo } from "@/types/api";
import { apiGet, apiGetBlob, apiPost } from "./client";

export function listarPendientes(): Promise<SolicitudVerificacion[]> {
  return apiGet<SolicitudVerificacion[]>("/verificaciones/pendientes");
}

export function resolverUsuario(id: string, aprobar: boolean, motivo?: string): Promise<Usuario> {
  return apiPost<Usuario>(`/verificaciones/usuarios/${id}/resolver`, { aprobar, motivo });
}

export function resolverVehiculo(id: string, aprobar: boolean, motivo?: string): Promise<Vehiculo> {
  return apiPost<Vehiculo>(`/verificaciones/vehiculos/${id}/resolver`, { aprobar, motivo });
}

export function descargarDocumento(documentoId: string): Promise<Blob> {
  return apiGetBlob(`/documentos/${documentoId}/archivo`);
}
