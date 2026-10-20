// Llamadas a vehiculos (servicio de identidad).
import type { TipoVehiculo, Vehiculo, VehiculoConDocumentos } from "@/types/api";
import { apiGet, apiPost, apiPostForm } from "./client";

// Busca un vehiculo por placa (vigilante, admin).
export function buscarPorPlaca(placa: string): Promise<Vehiculo> {
  return apiGet<Vehiculo>(`/vehiculos/placa/${encodeURIComponent(placa)}`);
}

// Datos para crear un vehiculo, por ejemplo de un visitante.
export interface CrearVehiculoPayload {
  placa: string;
  tipo_vehiculo: TipoVehiculo;
  marca?: string | null;
  modelo?: string | null;
  color?: string | null;
  usuario_id?: string | null;
  es_visitante: boolean;
}

// Crea un vehiculo (vigilante, admin).
export function crearVehiculo(datos: CrearVehiculoPayload): Promise<Vehiculo> {
  return apiPost<Vehiculo>("/vehiculos", datos);
}

// Los vehiculos del estudiante.
export function listarMisVehiculos(): Promise<VehiculoConDocumentos[]> {
  return apiGet<VehiculoConDocumentos[]>("/vehiculos/mis-vehiculos");
}

// Datos y archivos para registrar el vehiculo del estudiante.
export interface RegistrarMiVehiculoPayload {
  placa: string;
  tipo_vehiculo: TipoVehiculo;
  marca?: string;
  modelo?: string;
  color?: string;
  foto_placa: File;
  tarjeta_propiedad: File;
}

// Envia el vehiculo con sus dos fotos como formulario multipart.
export function registrarMiVehiculo(datos: RegistrarMiVehiculoPayload): Promise<VehiculoConDocumentos> {
  const formulario = new FormData();
  formulario.append("placa", datos.placa);
  formulario.append("tipo_vehiculo", datos.tipo_vehiculo);
  for (const campo of ["marca", "modelo", "color"] as const) {
    const valor = datos[campo]?.trim();
    if (valor) formulario.append(campo, valor);
  }
  formulario.append("foto_placa", datos.foto_placa);
  formulario.append("tarjeta_propiedad", datos.tarjeta_propiedad);
  return apiPostForm<VehiculoConDocumentos>("/vehiculos/mis-vehiculos", formulario);
}

// Reenvia los documentos de un vehiculo rechazado.
export function reenviarDocumentosVehiculo(
  vehiculoId: string,
  fotoPlaca: File,
  tarjetaPropiedad: File,
): Promise<VehiculoConDocumentos> {
  const formulario = new FormData();
  formulario.append("foto_placa", fotoPlaca);
  formulario.append("tarjeta_propiedad", tarjetaPropiedad);
  return apiPostForm<VehiculoConDocumentos>(`/vehiculos/mis-vehiculos/${vehiculoId}/reenviar`, formulario);
}
