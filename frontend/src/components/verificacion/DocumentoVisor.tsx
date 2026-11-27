import { useEffect, useState } from "react";

import { descargarDocumento } from "@/services/api/verificaciones";
import type { Documento, TipoDocumento } from "@/types/api";

// Nombre visible de cada tipo de documento.
const ETIQUETA_DOCUMENTO: Record<TipoDocumento, string> = {
  carnet: "Carnet / Divisist",
  foto_placa: "Foto de la placa",
  tarjeta_propiedad: "Tarjeta de propiedad",
  foto_serial: "Foto del número de serie",
};

/** Los documentos son privados: se bajan con el token y se muestran desde una URL local
 *  (blob:) que se libera al desmontar. En la moto electrica la tarjeta puede ser la factura. */
export default function DocumentoVisor({
  documento,
  deMotoElectrica = false,
}: {
  documento: Documento;
  deMotoElectrica?: boolean;
}) {
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
  const etiqueta =
    deMotoElectrica && documento.tipo === "tarjeta_propiedad"
      ? "Factura o tarjeta de propiedad"
      : ETIQUETA_DOCUMENTO[documento.tipo];

  return (
    <figure className="space-y-1">
      <figcaption className="text-xs font-medium text-gray-600">{etiqueta}</figcaption>
      {error && <p className="text-xs text-red-600">No se pudo cargar el archivo</p>}
      {!error && !url && <p className="text-xs text-gray-400">Cargando...</p>}
      {url && esPdf && (
        <a href={url} target="_blank" rel="noreferrer" className="text-sm text-emerald-700 underline">
          Abrir PDF
        </a>
      )}
      {url && !esPdf && (
        <a href={url} target="_blank" rel="noreferrer">
          <img src={url} alt={etiqueta} className="max-h-48 rounded-lg border object-contain" />
        </a>
      )}
    </figure>
  );
}
