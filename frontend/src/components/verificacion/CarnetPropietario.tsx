import { useEffect, useState } from "react";

import { descargarCarnetPropietario, verPropietario } from "@/services/api/vehiculos";

// Lo que se muestra mientras carga, si no hay carnet o con el carnet listo.
type Estado =
  | { tipo: "cargando" }
  | { tipo: "sin_carnet"; nombre: string | null }
  | { tipo: "listo"; nombre: string; url: string; esPdf: boolean };

/** RN-09: nombre y carnet del dueno para que el vigilante confirme quien trae la moto. El carnet
 *  se baja con el token y se muestra desde una URL local (blob:) que se libera al desmontar o al
 *  cambiar de placa. Si algo falla no bloquea la entrada ni la salida. */
export default function CarnetPropietario({ placa }: { placa: string }) {
  const [estado, setEstado] = useState<Estado>({ tipo: "cargando" });
  const [ampliado, setAmpliado] = useState(false);

  useEffect(() => {
    let creada: string | null = null;
    let cancelado = false;
    setEstado({ tipo: "cargando" });
    setAmpliado(false);
    // Pide el nombre y, si hay carnet, el archivo.
    (async () => {
      let nombre: string | null = null;
      try {
        const propietario = await verPropietario(placa);
        nombre = propietario.nombre_completo;
        if (!propietario.tiene_carnet) throw new Error("Sin carnet");
        const blob = await descargarCarnetPropietario(placa);
        if (cancelado) return;
        creada = URL.createObjectURL(blob);
        setEstado({ tipo: "listo", nombre, url: creada, esPdf: blob.type === "application/pdf" });
      } catch {
        if (!cancelado) setEstado({ tipo: "sin_carnet", nombre });
      }
    })();
    return () => {
      cancelado = true;
      if (creada) URL.revokeObjectURL(creada);
    };
  }, [placa]);

  if (estado.tipo === "cargando") {
    return <p className="mt-3 text-sm text-gray-400">Cargando dueño...</p>;
  }

  if (estado.tipo === "sin_carnet") {
    return (
      <div className="mt-3 rounded-xl bg-amber-50 p-3 text-sm text-amber-800">
        {estado.nombre && <p className="font-medium text-gray-900">{estado.nombre}</p>}
        <p>Sin carnet disponible: pide el carnet físico</p>
      </div>
    );
  }

  return (
    <div className={`mt-3 flex gap-3 rounded-xl bg-gray-50 p-3 ${ampliado ? "flex-col" : "items-center"}`}>
      {estado.esPdf ? (
        <a href={estado.url} target="_blank" rel="noreferrer" className="shrink-0 text-sm text-emerald-700 underline">
          Abrir PDF
        </a>
      ) : (
        <button
          type="button"
          onClick={() => setAmpliado(!ampliado)}
          className={ampliado ? "w-full" : "shrink-0"}
          aria-label={ampliado ? "Reducir carnet" : "Ampliar carnet"}
        >
          <img
            src={estado.url}
            alt={`Carnet de ${estado.nombre}`}
            className={
              ampliado ? "max-h-80 w-full rounded-lg border object-contain" : "h-20 w-28 rounded-lg border object-cover"
            }
          />
        </button>
      )}
      <div className="min-w-0">
        <p className="font-medium text-gray-900">{estado.nombre}</p>
        <p className="text-xs text-gray-600">Confirma que quien trae la moto es la persona del carnet</p>
      </div>
    </div>
  );
}
