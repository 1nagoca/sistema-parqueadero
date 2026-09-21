import type { TipoVehiculo, Vehiculo } from "@/types/api";
import { apiGet, apiPost } from "./client";

export function buscarPorPlaca(placa: string): Promise<Vehiculo> {
  return apiGet<Vehiculo>(`/vehiculos/placa/${encodeURIComponent(placa)}`);
}

export interface CrearVehiculoPayload {
  placa: string;
  tipo_vehiculo: TipoVehiculo;
  marca?: string | null;
  modelo?: string | null;
  color?: string | null;
  usuario_id?: string | null;
  es_visitante: boolean;
}

export function crearVehiculo(datos: CrearVehiculoPayload): Promise<Vehiculo> {
  return apiPost<Vehiculo>("/vehiculos", datos);
}
