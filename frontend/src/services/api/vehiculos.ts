// Llamadas a vehiculos (servicio de identidad).
import type {
  PropietarioVigilante,
  TipoVehiculo,
  Vehiculo,
  VehiculoConDocumentos,
  VehiculoConPlaca,
} from "@/types/api";
import { apiGet, apiGetBlob, apiPost, apiPostForm } from "./client";

// Busca un vehiculo por placa (vigilante, admin).
export function buscarPorPlaca(placa: string): Promise<VehiculoConPlaca> {
  return apiGet<VehiculoConPlaca>(`/vehiculos/placa/${encodeURIComponent(placa)}`);
}

// Nombre del dueno y si hay carnet para mostrar (vigilante, admin; RN-09).
export function verPropietario(placa: string): Promise<PropietarioVigilante> {
  return apiGet<PropietarioVigilante>(`/vehiculos/placa/${encodeURIComponent(placa)}/propietario`);
}

// El carnet del dueno de la moto como archivo (vigilante, admin; RN-09).
export function descargarCarnetPropietario(placa: string): Promise<Blob> {
  return apiGetBlob(`/vehiculos/placa/${encodeURIComponent(placa)}/carnet`);
}

// Busca una moto electrica por su numero de serie (vigilante, admin).
export function buscarPorSerie(numeroSerie: string): Promise<Vehiculo> {
  return apiGet<Vehiculo>(`/vehiculos/serie/${encodeURIComponent(numeroSerie)}`);
}

// Nombre del dueno de la moto electrica y si hay carnet para mostrar (vigilante, admin; RN-09).
export function verPropietarioPorSerie(numeroSerie: string): Promise<PropietarioVigilante> {
  return apiGet<PropietarioVigilante>(`/vehiculos/serie/${encodeURIComponent(numeroSerie)}/propietario`);
}

// El carnet del dueno de la moto electrica como archivo (vigilante, admin; RN-09).
export function descargarCarnetPorSerie(numeroSerie: string): Promise<Blob> {
  return apiGetBlob(`/vehiculos/serie/${encodeURIComponent(numeroSerie)}/carnet`);
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
export function crearVehiculo(datos: CrearVehiculoPayload): Promise<VehiculoConPlaca> {
  return apiPost<VehiculoConPlaca>("/vehiculos", datos);
}

// Los vehiculos del estudiante.
export function listarMisVehiculos(): Promise<VehiculoConDocumentos[]> {
  return apiGet<VehiculoConDocumentos[]>("/vehiculos/mis-vehiculos");
}

// Datos comunes de la moto del estudiante; las dos llevan tarjeta de propiedad o factura.
interface DatosMiMoto {
  tipo_vehiculo: TipoVehiculo;
  marca?: string;
  modelo?: string;
  color?: string;
  tarjeta_propiedad: File;
}

// Moto normal: con placa y foto de la placa.
export interface MiMotoNormal extends DatosMiMoto {
  es_electrica?: false;
  placa: string;
  foto_placa: File;
}

// Moto electrica: sin placa, con numero de serie y foto del serial.
export interface MiMotoElectrica extends DatosMiMoto {
  es_electrica: true;
  numero_serie: string;
  foto_serial: File;
}

export type RegistrarMiVehiculoPayload = MiMotoNormal | MiMotoElectrica;

// Envia la moto con sus dos documentos como formulario multipart; solo los campos de su tipo.
export function registrarMiVehiculo(datos: RegistrarMiVehiculoPayload): Promise<VehiculoConDocumentos> {
  const formulario = new FormData();
  if (datos.es_electrica) {
    formulario.append("es_electrica", "true");
    formulario.append("numero_serie", datos.numero_serie);
  } else {
    formulario.append("placa", datos.placa);
  }
  formulario.append("tipo_vehiculo", datos.tipo_vehiculo);
  for (const campo of ["marca", "modelo", "color"] as const) {
    const valor = datos[campo]?.trim();
    if (valor) formulario.append(campo, valor);
  }
  if (datos.es_electrica) formulario.append("foto_serial", datos.foto_serial);
  else formulario.append("foto_placa", datos.foto_placa);
  formulario.append("tarjeta_propiedad", datos.tarjeta_propiedad);
  return apiPostForm<VehiculoConDocumentos>("/vehiculos/mis-vehiculos", formulario);
}

// Reenvia los documentos de un vehiculo rechazado: la foto va como foto_serial si es electrica.
export function reenviarDocumentosVehiculo(
  vehiculoId: string,
  foto: File,
  tarjetaPropiedad: File,
  esElectrica: boolean,
): Promise<VehiculoConDocumentos> {
  const formulario = new FormData();
  formulario.append(esElectrica ? "foto_serial" : "foto_placa", foto);
  formulario.append("tarjeta_propiedad", tarjetaPropiedad);
  return apiPostForm<VehiculoConDocumentos>(`/vehiculos/mis-vehiculos/${vehiculoId}/reenviar`, formulario);
}
