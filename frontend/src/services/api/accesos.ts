// Llamadas al servicio de accesos (entradas y salidas).
import type { Acceso, AccesoActivo, AccesoEntradaPayload, MiAcceso, MotoBuscada } from "@/types/api";
import { apiGet, apiPost, ApiError } from "./client";

// Vehiculos que estan adentro en una zona.
export function listarAccesosActivos(zonaId: string): Promise<AccesoActivo[]> {
  return apiGet<AccesoActivo[]>(`/accesos?zona_id=${encodeURIComponent(zonaId)}`);
}

// El acceso abierto de una moto (por placa o por numero de serie), o null si no esta adentro.
export async function buscarAccesoActivo(moto: MotoBuscada): Promise<Acceso | null> {
  const consulta =
    "placa" in moto
      ? `placa=${encodeURIComponent(moto.placa)}`
      : `numero_serie=${encodeURIComponent(moto.numeroSerie)}`;
  try {
    return await apiGet<Acceso>(`/accesos/buscar?${consulta}`);
  } catch (error) {
    if (error instanceof ApiError && error.status === 404) {
      return null;
    }
    throw error;
  }
}

// Sus motos adentro (solo estudiante); lista vacia si ninguna esta en el parqueadero.
export function listarMisAccesos(): Promise<MiAcceso[]> {
  return apiGet<MiAcceso[]>("/accesos/mio");
}

// Registra una entrada.
export function registrarEntrada(datos: AccesoEntradaPayload): Promise<Acceso> {
  return apiPost<Acceso>("/accesos/entrada", datos);
}

// Registra la salida de un acceso.
export function registrarSalida(accesoId: string): Promise<Acceso> {
  return apiPost<Acceso>(`/accesos/${accesoId}/salida`);
}
