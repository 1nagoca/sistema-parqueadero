import type { EstadoEspacio } from "@/types/api";

// Color de cada estado: verde libre, rojo ocupado, amarillo reservado o en mantenimiento.
const colorPorEstado: Record<EstadoEspacio, string> = {
  libre: "bg-cupo-libre",
  ocupado: "bg-cupo-ocupado",
  reservado: "bg-cupo-reservado",
  mantenimiento: "bg-cupo-mantenimiento",
};

// Texto que aparece al pasar el mouse.
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

// Un cuadro del mapa: el codigo del espacio pintado segun su estado.
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
