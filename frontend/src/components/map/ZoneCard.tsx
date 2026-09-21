import SpaceCell from "@/components/map/SpaceCell";
import type { Espacio, Zona } from "@/types/api";

interface Props {
  zona: Zona;
  espacios: Espacio[];
}

/** Si la zona tiene espacios individuales registrados, se muestra la grilla con colores.
 * Si no (zona de solo conteo agregado), se muestra un indicador a nivel de zona. */
export default function ZoneCard({ zona, espacios }: Props) {
  const sinCupos = zona.cupos_disponibles <= 0;

  return (
    <div className="rounded-2xl bg-white p-4 shadow-sm">
      <div className="mb-3 flex items-center justify-between">
        <div>
          <h2 className="font-semibold text-gray-900">{zona.nombre}</h2>
          {zona.ubicacion_descripcion && <p className="text-xs text-gray-500">{zona.ubicacion_descripcion}</p>}
        </div>
        <span className="text-sm font-medium text-gray-600">
          {zona.cupos_disponibles}/{zona.capacidad_total} cupos
        </span>
      </div>

      {espacios.length > 0 ? (
        <div className="grid grid-cols-4 gap-2 sm:grid-cols-6 md:grid-cols-8">
          {espacios.map((espacio) => (
            <SpaceCell key={espacio.id} codigo={espacio.codigo} estado={espacio.estado} />
          ))}
        </div>
      ) : (
        <div
          className={`flex h-16 items-center justify-center rounded-lg font-medium text-white ${
            sinCupos ? "bg-cupo-ocupado" : "bg-cupo-libre"
          }`}
        >
          {sinCupos ? "Sin cupos disponibles" : "Cupos disponibles"}
        </div>
      )}
    </div>
  );
}
