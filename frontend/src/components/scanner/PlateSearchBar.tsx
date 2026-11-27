import { useState, type FormEvent } from "react";

import Button from "@/components/common/Button";
import type { MotoBuscada } from "@/types/api";

// Que se busca: la placa o el numero de serie de una moto electrica.
export type ModoBusqueda = "placa" | "serie";

interface Props {
  modo: ModoBusqueda;
  onCambiarModo: (modo: ModoBusqueda) => void;
  onBuscar: (moto: MotoBuscada) => void;
  buscando?: boolean;
}

// Placeholder, nombre y largo de la caja en cada modo.
const CAJA: Record<ModoBusqueda, { placeholder: string; etiqueta: string; maximo: number }> = {
  placa: { placeholder: "Ej. ABC12D o AB1C23D", etiqueta: "Placa", maximo: 10 },
  serie: { placeholder: "Ej. EB2024-00871", etiqueta: "Número de serie o VIN", maximo: 17 },
};

// Selector de modo y caja para escribir una placa o un numero de serie y buscarlo.
export default function PlateSearchBar({ modo, onCambiarModo, onBuscar, buscando }: Props) {
  const [texto, setTexto] = useState("");
  const caja = CAJA[modo];

  // Al cambiar de modo se limpia la caja.
  function cambiarModo(nuevo: ModoBusqueda) {
    setTexto("");
    onCambiarModo(nuevo);
  }

  // Envia la placa o el serial en mayusculas y sin espacios, y limpia la caja.
  function manejarSubmit(evento: FormEvent) {
    evento.preventDefault();
    const normalizado = modo === "placa" ? texto.trim().toUpperCase() : texto.replace(/\s/g, "").toUpperCase();
    if (normalizado) {
      onBuscar(modo === "placa" ? { placa: normalizado } : { numeroSerie: normalizado });
      setTexto("");
    }
  }

  const opcion = "min-h-12 flex-1 rounded-xl border px-3 text-sm font-medium";

  return (
    <div className="space-y-2">
      <div className="flex gap-2">
        {(["placa", "serie"] as const).map((valor) => (
          <button
            key={valor}
            type="button"
            aria-pressed={modo === valor}
            onClick={() => cambiarModo(valor)}
            className={`${opcion} ${modo === valor ? "border-emerald-500 bg-emerald-50 text-emerald-800" : "border-gray-300 text-gray-700"}`}
          >
            {valor === "placa" ? "Placa" : "Moto eléctrica"}
          </button>
        ))}
      </div>
      <form onSubmit={manejarSubmit} className="flex gap-2">
        <input
          value={texto}
          onChange={(evento) =>
            setTexto(
              modo === "placa"
                ? evento.target.value.toUpperCase()
                : evento.target.value.toUpperCase().replace(/\s/g, ""),
            )
          }
          placeholder={caja.placeholder}
          aria-label={caja.etiqueta}
          className={`min-h-14 min-w-0 flex-1 rounded-xl border border-gray-300 px-4 text-lg uppercase tracking-wider focus:border-emerald-500 focus:outline-none ${modo === "serie" ? "font-mono" : ""}`}
          maxLength={caja.maximo}
        />
        <Button type="submit" disabled={buscando || !texto.trim()} className="shrink-0">
          Buscar
        </Button>
      </form>
    </div>
  );
}
