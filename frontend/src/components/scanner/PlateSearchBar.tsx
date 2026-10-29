import { useState, type FormEvent } from "react";

import Button from "@/components/common/Button";

interface Props {
  onBuscar: (placa: string) => void;
  buscando?: boolean;
}

// Caja para escribir una placa y buscarla.
export default function PlateSearchBar({ onBuscar, buscando }: Props) {
  const [placa, setPlaca] = useState("");

  // Envia la placa en mayusculas y sin espacios, y limpia la caja.
  function manejarSubmit(evento: FormEvent) {
    evento.preventDefault();
    const normalizada = placa.trim().toUpperCase();
    if (normalizada) {
      onBuscar(normalizada);
      setPlaca("");
    }
  }

  return (
    <form onSubmit={manejarSubmit} className="flex gap-2">
      <input
        value={placa}
        onChange={(evento) => setPlaca(evento.target.value.toUpperCase())}
        placeholder="Ej. ABC12D"
        aria-label="Placa"
        className="min-h-14 min-w-0 flex-1 rounded-xl border border-gray-300 px-4 text-lg uppercase tracking-wider focus:border-emerald-500 focus:outline-none"
        maxLength={10}
      />
      <Button type="submit" disabled={buscando || !placa.trim()} className="shrink-0">
        Buscar
      </Button>
    </form>
  );
}
