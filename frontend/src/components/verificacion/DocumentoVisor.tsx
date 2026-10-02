import { useEffect, useState } from "react";

import { descargarDocumento } from "@/services/api/verificaciones";
import type { Documento, TipoDocumento } from "@/types/api";

export const ETIQUETA_DOCUMENTO: Record<TipoDocumento, string> = {
  carnet: "Carnet / Divisist",
  foto_placa: "Foto de la placa",
  tarjeta_propiedad: "Tarjeta de propiedad",
};

/** Los documentos son privados: se bajan con el token y se muestran desde una URL local
 *  (blob:) que se libera al desmontar. */
export default function DocumentoVisor({ documento }: { documento: Documento }) {
  const [url, setUrl] = useState<string | null>(null);
  const [error, setError] = useState(false);

  useEffect(() => {
    let creada: string | null = null;
    let cancelado = false;
    descargarDocumento(documento.id)
      .then((blob) => {
        if (cancelado) return;
        creada = URL.createObjectURL(blob);
        setUrl(creada);
      })
      .catch(() => setError(true));
    return () => {
      cancelado = true;
      if (creada) URL.revokeObjectURL(creada);
    };
  }, [documento.id]);

  const esPdf = documento.content_type === "application/pdf";

  return (
    <figure className="space-y-1">
      <figcaption className="text-xs font-medium text-gray-600">{ETIQUETA_DOCUMENTO[documento.tipo]}</figcaption>
      {error && <p className="text-xs text-red-600">No se pudo cargar el archivo</p>}
      {!error && !url && <p className="text-xs text-gray-400">Cargando...</p>}
      {url && esPdf && (
        <a href={url} target="_blank" rel="noreferrer" className="text-sm text-emerald-700 underline">
          Abrir PDF
        </a>
      )}
      {url && !esPdf && (
        <a href={url} target="_blank" rel="noreferrer">
          <img src={url} alt={ETIQUETA_DOCUMENTO[documento.tipo]} className="max-h-48 rounded-lg border object-contain" />
        </a>
      )}
    </figure>
  );
}
