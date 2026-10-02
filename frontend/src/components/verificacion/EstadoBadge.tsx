import type { EstadoVerificacion } from "@/types/api";

const ESTILOS: Record<EstadoVerificacion, string> = {
  pendiente: "bg-amber-100 text-amber-800",
  aprobado: "bg-emerald-100 text-emerald-800",
  rechazado: "bg-red-100 text-red-800",
};

const TEXTOS: Record<EstadoVerificacion, string> = {
  pendiente: "En revision",
  aprobado: "Aprobado",
  rechazado: "Rechazado",
};

export default function EstadoBadge({ estado }: { estado: EstadoVerificacion }) {
  return (
    <span className={`inline-block rounded-full px-3 py-1 text-xs font-semibold ${ESTILOS[estado]}`}>
      {TEXTOS[estado]}
    </span>
  );
}
