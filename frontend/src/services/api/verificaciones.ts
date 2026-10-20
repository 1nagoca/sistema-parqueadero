// Bandeja de verificacion del admin (servicio de identidad).
import type { SolicitudVerificacion, Usuario, Vehiculo } from "@/types/api";
import { apiGet, apiGetBlob, apiPost } from "./client";

// Estudiantes y vehiculos por revisar.
export function listarPendientes(): Promise<SolicitudVerificacion[]> {
  return apiGet<SolicitudVerificacion[]>("/verificaciones/pendientes");
}

// Aprueba o rechaza a un estudiante.
export function resolverUsuario(id: string, aprobar: boolean, motivo?: string): Promise<Usuario> {
  return apiPost<Usuario>(`/verificaciones/usuarios/${id}/resolver`, { aprobar, motivo });
}

// Aprueba o rechaza un vehiculo.
export function resolverVehiculo(id: string, aprobar: boolean, motivo?: string): Promise<Vehiculo> {
  return apiPost<Vehiculo>(`/verificaciones/vehiculos/${id}/resolver`, { aprobar, motivo });
}

// Descarga un documento privado con el token.
export function descargarDocumento(documentoId: string): Promise<Blob> {
  return apiGetBlob(`/documentos/${documentoId}/archivo`);
}
