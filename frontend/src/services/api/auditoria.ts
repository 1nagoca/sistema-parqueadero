import type { AuditoriaAcceso } from "@/types/api";
import { apiGet } from "./client";

export function listarAuditoria(tablaAfectada?: string): Promise<AuditoriaAcceso[]> {
  const query = tablaAfectada ? `?tabla_afectada=${encodeURIComponent(tablaAfectada)}` : "";
  return apiGet<AuditoriaAcceso[]>(`/auditoria${query}`);
}
