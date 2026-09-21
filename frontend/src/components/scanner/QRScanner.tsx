import jsQR from "jsqr";
import { useEffect, useRef, useState } from "react";

interface Props {
  activo: boolean;
  onDetectado: (texto: string) => void;
}

/** Lector de QR por camara (navigator.mediaDevices), sin dependencias nativas: decodifica
 * frames de video con jsQR sobre un canvas oculto. El contenido del QR se interpreta como la
 * placa del vehiculo (texto plano) o como JSON `{"placa": "..."}` si el credencial lo trae asi. */
export default function QRScanner({ activo, onDetectado }: Props) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const frameRef = useRef<number>(0);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!activo) {
      detener();
      return;
    }

    let cancelado = false;

    async function iniciar() {
      try {
        const stream = await navigator.mediaDevices.getUserMedia({
          video: { facingMode: "environment" },
        });
        if (cancelado) {
          stream.getTracks().forEach((track) => track.stop());
          return;
        }
        streamRef.current = stream;
        if (videoRef.current) {
          videoRef.current.srcObject = stream;
          await videoRef.current.play();
        }
        setError(null);
        frameRef.current = requestAnimationFrame(procesarFrame);
      } catch {
        setError("No se pudo acceder a la camara. Verifica los permisos del navegador.");
      }
    }

    function procesarFrame() {
      const video = videoRef.current;
      const canvas = canvasRef.current;
      if (video && canvas && video.readyState === video.HAVE_ENOUGH_DATA) {
        canvas.width = video.videoWidth;
        canvas.height = video.videoHeight;
        const contexto = canvas.getContext("2d");
        if (contexto) {
          contexto.drawImage(video, 0, 0, canvas.width, canvas.height);
          const imagen = contexto.getImageData(0, 0, canvas.width, canvas.height);
          const resultado = jsQR(imagen.data, imagen.width, imagen.height);
          if (resultado?.data) {
            onDetectado(extraerPlaca(resultado.data));
            return;
          }
        }
      }
      frameRef.current = requestAnimationFrame(procesarFrame);
    }

    iniciar();

    return () => {
      cancelado = true;
      detener();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activo]);

  function detener() {
    cancelAnimationFrame(frameRef.current);
    streamRef.current?.getTracks().forEach((track) => track.stop());
    streamRef.current = null;
  }

  if (!activo) {
    return null;
  }

  return (
    <div className="overflow-hidden rounded-xl bg-black">
      {error ? (
        <p className="p-4 text-sm text-red-300">{error}</p>
      ) : (
        <video ref={videoRef} className="w-full" muted playsInline />
      )}
      <canvas ref={canvasRef} className="hidden" />
    </div>
  );
}

function extraerPlaca(textoQR: string): string {
  try {
    const datos = JSON.parse(textoQR);
    if (typeof datos.placa === "string") {
      return datos.placa;
    }
  } catch {
    // no era JSON, se usa el texto plano tal cual
  }
  return textoQR;
}
