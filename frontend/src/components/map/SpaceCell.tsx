import type { EstadoEspacio } from "@/types/api";

const colorPorEstado: Record<EstadoEspacio, string> = {
  libre: "bg-cupo-libre",
  ocupado: "bg-cupo-ocupado",
  reservado: "bg-cupo-reservado",
  mantenimiento: "bg-cupo-mantenimiento",
};

const etiquetaPorEstado: Record<EstadoEspacio, string> = {
  libre: "Libre",
  ocupado: "Ocupado",
  reservado: "Reservado",
  mantenimiento: "Mantenimiento",
};

interface Props {
  codigo: string;
  estado: EstadoEspacio;
}

export default function SpaceCell({ codigo, estado }: Props) {
  return (
    <div
      title={`${codigo} — ${etiquetaPorEstado[estado]}`}
      className={`flex aspect-square min-w-14 flex-col items-center justify-center rounded-lg text-xs font-semibold text-white shadow-sm ${colorPorEstado[estado]}`}
    >
      <span>{codigo}</span>
    </div>
  );
}
