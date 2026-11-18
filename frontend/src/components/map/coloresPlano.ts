import type { EstadoEspacio } from "@/types/api";

// Color de cada estado; gris si el puesto del plano aun no existe en la base.
export const colorPorEstado: Record<EstadoEspacio, string> = {
  libre: "#22c55e",
  ocupado: "#ef4444",
  reservado: "#eab308",
  mantenimiento: "#eab308",
};
export const COLOR_SIN_CREAR = "#d1d5db";
export const COLOR_VISITANTE = "#8b5cf6";
