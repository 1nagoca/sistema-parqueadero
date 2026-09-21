import { useCallback, useEffect, useState } from "react";

import ZoneCard from "@/components/map/ZoneCard";
import { useAuth } from "@/context/AuthContext";
import { listarEspacios } from "@/services/api/espacios";
import { listarZonas } from "@/services/api/zonas";
import { useActualizacionesZona } from "@/services/realtime/useActualizacionesZona";
import type { Espacio, Zona } from "@/types/api";

export default function ParkingMapPage() {
  const { usuario, cerrarSesion } = useAuth();
  const [zonas, setZonas] = useState<Zona[]>([]);
  const [espaciosPorZona, setEspaciosPorZona] = useState<Record<string, Espacio[]>>({});
  const [error, setError] = useState<string | null>(null);
  const [actualizadoEn, setActualizadoEn] = useState<Date | null>(null);

  const cargar = useCallback(async () => {
    try {
      const datosZonas = await listarZonas();
      setZonas(datosZonas);

      const listas = await Promise.all(datosZonas.map((zona) => listarEspacios(zona.id)));
      const mapa: Record<string, Espacio[]> = {};
      datosZonas.forEach((zona, indice) => {
        mapa[zona.id] = listas[indice];
      });
      setEspaciosPorZona(mapa);
      setActualizadoEn(new Date());
      setError(null);
    } catch {
      setError("No se pudo cargar el mapa de cupos");
    }
  }, []);

  useEffect(() => {
    cargar();
  }, [cargar]);

  // El mapa se refresca solo cuando backend-core avisa por /ws/zonas (tras cada entrada/salida),
  // sin necesidad de polling.
  useActualizacionesZona(cargar);

  return (
    <div className="min-h-screen bg-gray-100 p-4 pb-24 sm:p-6">
      <header className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-gray-900 sm:text-2xl">Mapa de Parqueadero</h1>
          {usuario && <p className="text-sm text-gray-500">{usuario.nombre_completo}</p>}
        </div>
        <button onClick={cerrarSesion} className="text-sm text-gray-500 underline">
          Cerrar sesion
        </button>
      </header>

      <div className="mb-4 flex flex-wrap items-center gap-4 rounded-2xl bg-white p-3 text-sm shadow-sm">
        <Leyenda color="bg-cupo-libre" texto="Libre" />
        <Leyenda color="bg-cupo-ocupado" texto="Ocupado" />
        <Leyenda color="bg-cupo-reservado" texto="Reservado / Mantenimiento" />
        {actualizadoEn && (
          <span className="ml-auto text-xs text-gray-400">
            Actualizado {actualizadoEn.toLocaleTimeString("es-CO")}
          </span>
        )}
      </div>

      {error && <p className="mb-4 rounded-xl bg-red-100 p-3 text-red-800">{error}</p>}

      <div className="space-y-4">
        {zonas.map((zona) => (
          <ZoneCard key={zona.id} zona={zona} espacios={espaciosPorZona[zona.id] ?? []} />
        ))}
        {zonas.length === 0 && !error && <p className="text-center text-gray-400">Cargando zonas...</p>}
      </div>
    </div>
  );
}

function Leyenda({ color, texto }: { color: string; texto: string }) {
  return (
    <span className="flex items-center gap-1.5">
      <span className={`h-3 w-3 rounded-full ${color}`} />
      {texto}
    </span>
  );
}
