// Llamadas a espacios (servicio de parqueadero).
import type {
  Espacio,
  EspacioCreatePayload,
  EspacioLotePayload,
  EspacioLoteResultado,
  MantenimientoActivo,
} from "@/types/api";
import { apiGet, apiPost } from "./client";

// Espacios de todas las zonas o de una.
export function listarEspacios(zonaId?: string): Promise<Espacio[]> {
  const query = zonaId ? `?zona_id=${encodeURIComponent(zonaId)}` : "";
  return apiGet<Espacio[]>(`/espacios${query}`);
}

// Crea un espacio (admin).
export function crearEspacio(datos: EspacioCreatePayload): Promise<Espacio> {
  return apiPost<Espacio>("/espacios", datos);
}

// Crea de una vez los puestos del plano que falten (admin).
export function crearEspaciosLote(datos: EspacioLotePayload): Promise<EspacioLoteResultado> {
  return apiPost<EspacioLoteResultado>("/espacios/lote", datos);
}

// Pone un puesto libre en mantenimiento con su motivo (admin).
export function ponerEnMantenimiento(espacioId: string, motivo: string): Promise<Espacio> {
  return apiPost<Espacio>(`/espacios/${encodeURIComponent(espacioId)}/mantenimiento`, { motivo });
}

// Devuelve a libre un puesto en mantenimiento (admin).
export function habilitarEspacio(espacioId: string): Promise<Espacio> {
  return apiPost<Espacio>(`/espacios/${encodeURIComponent(espacioId)}/habilitar`);
}

// Puestos que estan en mantenimiento ahora en una zona (admin).
export function listarMantenimientos(zonaId: string): Promise<MantenimientoActivo[]> {
  return apiGet<MantenimientoActivo[]>(`/espacios/mantenimientos?zona_id=${encodeURIComponent(zonaId)}`);
}
