import { useRef, useState, type ChangeEvent } from "react";

import Button from "@/components/common/Button";
import { ApiError } from "@/services/api/client";
import { reconocerPlaca, type LecturaPlaca } from "@/services/api/vision";

interface Props {
  onDetectada: (lectura: LecturaPlaca) => void;
}

/** Lectura automatica de placa: el vigilante toma o elige una foto y el microservicio de
 * vision devuelve la placa con su confianza. En el celular abre la camara trasera. */
export default function PlateReader({ onDetectada }: Props) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [leyendo, setLeyendo] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function manejarArchivo(evento: ChangeEvent<HTMLInputElement>) {
    const imagen = evento.target.files?.[0];
    evento.target.value = "";
    if (!imagen) return;

    setLeyendo(true);
    setError(null);
    try {
      onDetectada(await reconocerPlaca(imagen));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "No se pudo leer la placa");
    } finally {
      setLeyendo(false);
    }
  }

  return (
    <div>
      <input
        ref={inputRef}
        type="file"
        accept="image/*"
        capture="environment"
        className="hidden"
        onChange={manejarArchivo}
      />
      <Button
        type="button"
        variante="secundaria"
        className="w-full"
        disabled={leyendo}
        onClick={() => inputRef.current?.click()}
      >
        {leyendo ? "Leyendo placa..." : "Leer placa con foto"}
      </Button>
      {error && <p className="mt-2 text-sm text-red-600">{error}</p>}
    </div>
  );
}
