// Llamadas a las dos bitacoras: la de accesos y la de verificaciones.
import type { AuditoriaPagina, FiltrosAuditoria } from "@/types/api";
import { apiGet } from "./client";

// Arma la query con los filtros que traen valor.
function consulta(filtros: FiltrosAuditoria): string {
  const params = new URLSearchParams();
  if (filtros.desde) params.set("desde", filtros.desde);
  if (filtros.hasta) params.set("hasta", filtros.hasta);
  if (filtros.tabla_afectada) params.set("tabla_afectada", filtros.tabla_afectada);
  if (filtros.pagina) params.set("pagina", String(filtros.pagina));
  if (filtros.por_pagina) params.set("por_pagina", String(filtros.por_pagina));
  const query = params.toString();
  return query ? `?${query}` : "";
}

// Trazas de entradas y salidas (servicio de accesos), por periodo y paginadas.
export function listarAuditoria(filtros: FiltrosAuditoria = {}): Promise<AuditoriaPagina> {
  return apiGet<AuditoriaPagina>(`/auditoria${consulta(filtros)}`);
}

/** Trazas de aprobar, rechazar, dar de baja o reactivar: viven en el servicio de identidad. */
export function listarAuditoriaVerificaciones(filtros: FiltrosAuditoria = {}): Promise<AuditoriaPagina> {
  return apiGet<AuditoriaPagina>(`/verificaciones/auditoria${consulta(filtros)}`);
}
