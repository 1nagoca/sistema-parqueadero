import { useState, type FormEvent } from "react";

import Button from "@/components/common/Button";

interface Props {
  onBuscar: (placa: string) => void;
  buscando?: boolean;
}

export default function PlateSearchBar({ onBuscar, buscando }: Props) {
  const [placa, setPlaca] = useState("");

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
        placeholder="Placa (ej. ABC123)"
        className="min-h-14 flex-1 rounded-xl border border-gray-300 px-4 text-lg uppercase tracking-wider focus:border-emerald-500 focus:outline-none"
        maxLength={10}
      />
      <Button type="submit" disabled={buscando || !placa.trim()}>
        Buscar
      </Button>
    </form>
  );
}
