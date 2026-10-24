import { useId, type CSSProperties } from "react";

import {
  BLOQUES,
  CAJAS,
  CAMINO_UNIVERSIDAD,
  FILAS,
  FLECHAS,
  PAREDES,
  PUESTO,
  PUESTOS,
  type Rectangulo,
} from "@/components/map/planoParqueadero";
import type { Espacio, EstadoEspacio } from "@/types/api";

// Color de cada estado; gris si el puesto del plano aun no existe en la base.
export const colorPorEstado: Record<EstadoEspacio, string> = {
  libre: "#22c55e",
  ocupado: "#ef4444",
  reservado: "#eab308",
  mantenimiento: "#eab308",
};
export const COLOR_SIN_CREAR = "#d1d5db";
export const COLOR_VISITANTE = "#8b5cf6";

// Lo necesario para que cada puesto se pueda tocar.
interface Interaccion {
  onTocar: (codigo: string) => void;
  textoDe: (espacio: Espacio | undefined) => string;
  consultado: string | null;
  seleccionadoId?: string;
  // Si es verdadero, los puestos libres se muestran como elegibles.
  sePuedeElegir: boolean;
}

interface Props {
  // Parte del plano que se ve.
  vista: Rectangulo;
  // Si se pasa, solo se dibujan los puestos de esas letras.
  letras?: string[];
  porCodigo: Map<string, Espacio>;
  esDeVisitante: (espacio: Espacio | undefined) => boolean;
  // Sin interaccion es una miniatura: los puestos no se tocan.
  interaccion?: Interaccion;
  // En la miniatura: bloques que se tocan para acercarlos.
  bloques?: { elegido: string | null; onElegir: (id: string) => void };
  className?: string;
  style?: CSSProperties;
}

// Dibujo SVG del plano o de una parte de el, con cada puesto pintado segun su estado.
export default function DibujoPlano({ vista, letras, porCodigo, esDeVisitante, interaccion, bloques, className, style }: Props) {
  // Ids unicos del degradado y de la punta de flecha por si hay varios dibujos en la pagina.
  const id = useId().replace(/:/g, "");
  const idVisitante = `puesto-visitante-${id}`;
  const idPunta = `punta-flecha-${id}`;

  const puestos = letras ? PUESTOS.filter((puesto) => letras.includes(puesto.letra)) : PUESTOS;

  return (
    <svg
      viewBox={`${vista.x} ${vista.y} ${vista.ancho} ${vista.alto}`}
      className={className}
      style={style}
      role="img"
      aria-label="Mapa del parqueadero"
    >
      <defs>
        {/* Mitad roja arriba a la izquierda y mitad morada abajo a la derecha, partidas en diagonal. */}
        <linearGradient id={idVisitante} x1="0" y1="0" x2="1" y2="1">
          <stop offset="50%" stopColor={colorPorEstado.ocupado} />
          <stop offset="50%" stopColor={COLOR_VISITANTE} />
        </linearGradient>
        <marker id={idPunta} viewBox="0 0 10 10" refX={9} refY={5} markerWidth={6} markerHeight={6} orient="auto">
          <path d="M 0 1 L 9 5 L 0 9" fill="none" stroke="#4b5563" strokeWidth={1.5} />
        </marker>
      </defs>

      {FLECHAS.map((flecha, indice) => (
        <line key={indice} {...flecha} stroke="#4b5563" strokeWidth={1} markerEnd={`url(#${idPunta})`} />
      ))}
      <path d={CAMINO_UNIVERSIDAD} fill="none" stroke="#4b5563" strokeWidth={2} strokeDasharray="5 4" markerEnd={`url(#${idPunta})`} />
      {PAREDES.map((pared, indice) => (
        <line key={indice} {...pared} stroke="#111827" strokeWidth={3} strokeLinecap="round" />
      ))}

      {CAJAS.map((caja) => (
        <g key={caja.lineas.join(" ")}>
          <rect x={caja.x} y={caja.y} width={caja.ancho} height={caja.alto} rx={5} fill="#f3f4f6" stroke="#6b7280" />
          {caja.lineas.map((linea, indice) => (
            <text
              key={linea}
              x={caja.x + caja.ancho / 2}
              y={caja.y + caja.alto / 2 + 4 + (indice - (caja.lineas.length - 1) / 2) * 16}
              textAnchor="middle"
              fontSize={indice === 0 ? 13 : 11}
              fill="#374151"
            >
              {linea}
            </text>
          ))}
        </g>
      ))}

      {FILAS.filter((fila) => !letras || letras.includes(fila.letra)).map((fila) => {
        const inicio = fila.tramos[0];
        return fila.vertical ? (
          <text key={fila.letra} x={inicio.x + PUESTO / 2} y={inicio.y - 6} textAnchor="middle" fontSize={11} fontWeight={700} fill="#374151">
            {fila.letra}
          </text>
        ) : (
          <text key={fila.letra} x={inicio.x - 5} y={inicio.y + 11} textAnchor="end" fontSize={11} fontWeight={700} fill="#374151">
            {fila.letra}
          </text>
        );
      })}

      <g pointerEvents={interaccion ? undefined : "none"}>
        {puestos.map((puesto) => {
          const espacio = porCodigo.get(puesto.codigo);
          const relleno = esDeVisitante(espacio)
            ? `url(#${idVisitante})`
            : espacio
              ? colorPorEstado[espacio.estado]
              : COLOR_SIN_CREAR;
          if (!interaccion) {
            return <rect key={puesto.codigo} x={puesto.x} y={puesto.y} width={PUESTO} height={PUESTO} rx={3} fill={relleno} />;
          }
          const elegible = interaccion.sePuedeElegir && espacio?.estado === "libre";
          const elegido = espacio !== undefined && espacio.id === interaccion.seleccionadoId;
          return (
            <rect
              key={puesto.codigo}
              x={puesto.x}
              y={puesto.y}
              width={PUESTO}
              height={PUESTO}
              rx={3}
              fill={relleno}
              stroke={elegido ? "#1e3a8a" : interaccion.consultado === puesto.codigo ? "#111827" : "none"}
              strokeWidth={elegido ? 3 : 1.5}
              className={elegible ? "cursor-pointer hover:opacity-70" : "cursor-default"}
              onClick={() => interaccion.onTocar(puesto.codigo)}
            >
              <title>{`${puesto.codigo} — ${interaccion.textoDe(espacio)}`}</title>
            </rect>
          );
        })}
      </g>

      {bloques &&
        BLOQUES.map((bloque) => {
          const elegido = bloques.elegido === bloque.id;
          return (
            <rect
              key={bloque.id}
              x={bloque.x}
              y={bloque.y}
              width={bloque.ancho}
              height={bloque.alto}
              rx={8}
              fill="#3b82f6"
              fillOpacity={elegido ? 0.25 : 0}
              stroke={elegido ? "#1d4ed8" : "#9ca3af"}
              strokeWidth={elegido ? 14 : 6}
              className="cursor-pointer"
              onClick={() => bloques.onElegir(bloque.id)}
            >
              <title>{bloque.nombre}</title>
            </rect>
          );
        })}
    </svg>
  );
}
