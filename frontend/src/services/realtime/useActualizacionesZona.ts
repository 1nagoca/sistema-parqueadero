import { useEffect, useRef } from "react";

import { obtenerToken } from "@/services/api/client";

// Direccion del WebSocket en el gateway; en el servidor se cambia con VITE_WS_URL.
const WS_URL = import.meta.env.VITE_WS_URL ?? "ws://localhost:8000/ws/zonas";

// Cierre del servidor por sesion ausente, invalida o vencida: no se reintenta.
const CIERRE_SIN_SESION = 4401;

// Mensaje que envia el servidor cuando cambian los cupos.
interface EventoZona {
  evento: string;
  zona_id: string;
  cupos_disponibles: number;
}

/** Se suscribe a /ws/zonas (poblado por backend-parqueadero via BackgroundTasks despues de cada
 * entrada/salida) y llama a `onActualizacion` con cada evento. Manda el token al abrir y reintenta
 * con backoff simple si el socket se cae, salvo que el servidor cierre por sesion (4401). */
export function useActualizacionesZona(onActualizacion: () => void): void {
  const callbackRef = useRef(onActualizacion);
  callbackRef.current = onActualizacion;

  useEffect(() => {
    let socket: WebSocket | null = null;
    let cerradoPorLimpieza = false;
    let intentoReconexion = 0;
    let temporizador: ReturnType<typeof setTimeout> | undefined;

    // Abre el WebSocket y, si se cae, reintenta cada vez mas lento (hasta 10 s).
    function conectar() {
      const token = obtenerToken();
      // sin sesion no se abre el WebSocket
      if (!token) return;
      const nuevo = new WebSocket(WS_URL);
      socket = nuevo;

      // el token va en el primer mensaje, nunca en la URL
      nuevo.onopen = () => nuevo.send(JSON.stringify({ token }));

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

      socket.onclose = (evento) => {
        if (cerradoPorLimpieza || evento.code === CIERRE_SIN_SESION) return;
        intentoReconexion += 1;
        const espera = Math.min(1000 * intentoReconexion, 10000);
        temporizador = setTimeout(conectar, espera);
      };
    }

    conectar();

    // Al salir de la pagina cierra el WebSocket y no reintenta.
    return () => {
      cerradoPorLimpieza = true;
      clearTimeout(temporizador);
      socket?.close();
    };
  }, []);
}
