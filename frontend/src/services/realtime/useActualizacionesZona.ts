import { useEffect, useRef } from "react";

const WS_URL = import.meta.env.VITE_WS_URL ?? "ws://localhost:8000/ws/zonas";

interface EventoZona {
  evento: string;
  zona_id: string;
  cupos_disponibles: number;
}

/** Se suscribe a /ws/zonas (poblado por backend-core via BackgroundTasks despues de cada
 * entrada/salida) y llama a `onActualizacion` con cada evento. Reintenta la conexion con
 * backoff simple si el socket se cae. */
export function useActualizacionesZona(onActualizacion: () => void): void {
  const callbackRef = useRef(onActualizacion);
  callbackRef.current = onActualizacion;

  useEffect(() => {
    let socket: WebSocket | null = null;
    let cerradoPorLimpieza = false;
    let intentoReconexion = 0;
    let temporizador: ReturnType<typeof setTimeout> | undefined;

    function conectar() {
      socket = new WebSocket(WS_URL);

      socket.onmessage = (evento) => {
        try {
          const datos = JSON.parse(evento.data) as EventoZona;
          if (datos.evento === "zona_actualizada") {
            callbackRef.current();
          }
        } catch {
          // mensaje no reconocido, se ignora
        }
      };

      socket.onclose = () => {
        if (cerradoPorLimpieza) return;
        intentoReconexion += 1;
        const espera = Math.min(1000 * intentoReconexion, 10000);
        temporizador = setTimeout(conectar, espera);
      };
    }

    conectar();

    return () => {
      cerradoPorLimpieza = true;
      clearTimeout(temporizador);
      socket?.close();
    };
  }, []);
}
