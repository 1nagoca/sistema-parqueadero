import { useId, useMemo, useState } from "react";

import {
  ALTO,
  ANCHO,
  ENTRADA,
  FILAS,
  PAREDES,
  PUERTA,
  PUESTO,
  PUESTOS,
  SALIDA,
} from "@/components/map/planoParqueadero";
import type { Espacio, EstadoEspacio } from "@/types/api";

// Color de cada estado; gris si el puesto del plano aun no existe en la base.
const colorPorEstado: Record<EstadoEspacio, string> = {
  libre: "#22c55e",
  ocupado: "#ef4444",
  reservado: "#eab308",
  mantenimiento: "#eab308",
};
const COLOR_SIN_CREAR = "#d1d5db";
const COLOR_VISITANTE = "#8b5cf6";
// Muestra de la leyenda: mitad ocupado y mitad visitante.
const MUESTRA_VISITANTE = `linear-gradient(135deg, ${colorPorEstado.ocupado} 50%, ${COLOR_VISITANTE} 50%)`;
const TEXTO_VISITANTE = "Ocupado por visitante";

// Texto de cada estado.
const etiquetaPorEstado: Record<EstadoEspacio, string> = {
  libre: "Libre",
  ocupado: "Ocupado",
  reservado: "Reservado",
  mantenimiento: "Mantenimiento",
};

interface Props {
  espacios: Espacio[];
  // Si se pasa, tocar un puesto libre lo elige (vigilante).
  onSeleccionar?: (espacio: Espacio) => void;
  seleccionadoId?: string;
  // Ids de los espacios que ocupa un visitante; sin esta prop no se marcan (mapa publico).
  espaciosVisitante?: Set<string>;
}

// Plano del parqueadero con cada puesto pintado segun su estado.
export default function MapaParqueadero({ espacios, onSeleccionar, seleccionadoId, espaciosVisitante }: Props) {
  const [consultado, setConsultado] = useState<string | null>(null);
  // Id unico del degradado por si hay dos mapas en la misma pagina.
  const idVisitante = `puesto-visitante-${useId().replace(/:/g, "")}`;

  // Espacios de la base por codigo.
  const porCodigo = useMemo(() => new Map(espacios.map((espacio) => [espacio.codigo, espacio])), [espacios]);

  // Libres y total de cada letra.
  const resumen = useMemo(
    () =>
      FILAS.map((fila) => {
        const puestos = PUESTOS.filter((puesto) => puesto.letra === fila.letra);
        const libres = puestos.filter((puesto) => porCodigo.get(puesto.codigo)?.estado === "libre").length;
        return { letra: fila.letra, libres, total: puestos.length };
      }),
    [porCodigo],
  );

  // Al tocar un puesto: lo muestra y, si es libre y se puede elegir, lo elige.
  function tocar(codigo: string) {
    setConsultado(codigo);
    const espacio = porCodigo.get(codigo);
    if (onSeleccionar && espacio?.estado === "libre") onSeleccionar(espacio);
  }

  // Solo cuenta como de visitante si el puesto sigue ocupado.
  function esDeVisitante(espacio: Espacio | undefined): boolean {
    return espacio?.estado === "ocupado" && espaciosVisitante?.has(espacio.id) === true;
  }

  // Texto del estado de un puesto.
  function textoDe(espacio: Espacio | undefined): string {
    if (!espacio) return "Sin crear";
    return esDeVisitante(espacio) ? TEXTO_VISITANTE : etiquetaPorEstado[espacio.estado];
  }

  const espacioConsultado = consultado ? porCodigo.get(consultado) : undefined;
  const libresTotales = resumen.reduce((suma, fila) => suma + fila.libres, 0);

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-sm text-gray-600">
        <Leyenda color={colorPorEstado.libre} texto="Libre" />
        <Leyenda color={colorPorEstado.ocupado} texto="Ocupado" />
        {espaciosVisitante && <Leyenda color={MUESTRA_VISITANTE} texto={TEXTO_VISITANTE} />}
        <Leyenda color={colorPorEstado.mantenimiento} texto="Reservado / Mantenimiento" />
        <Leyenda color={COLOR_SIN_CREAR} texto="Sin crear" />
        <span className="font-medium text-gray-800">
          {libresTotales} de {PUESTOS.length} libres
        </span>
      </div>

      <div className="overflow-x-auto rounded-xl border border-gray-200 bg-white">
        <svg viewBox={`0 0 ${ANCHO} ${ALTO}`} className="w-full min-w-[52rem]" role="img" aria-label="Mapa del parqueadero">
          <defs>
            {/* Mitad roja arriba a la izquierda y mitad morada abajo a la derecha, partidas en diagonal. */}
            <linearGradient id={idVisitante} x1="0" y1="0" x2="1" y2="1">
              <stop offset="50%" stopColor={colorPorEstado.ocupado} />
              <stop offset="50%" stopColor={COLOR_VISITANTE} />
            </linearGradient>
          </defs>
          {PAREDES.map((pared, indice) => (
            <line key={indice} {...pared} stroke="#1f2937" strokeWidth={2} strokeLinecap="round" />
          ))}
          <path d={PUERTA} fill="none" stroke="#1f2937" strokeWidth={2} />

          {[ENTRADA, SALIDA].map((caja) => (
            <g key={caja.texto}>
              <rect x={caja.x} y={caja.y} width={caja.ancho} height={caja.alto} rx={5} fill="#f3f4f6" stroke="#6b7280" />
              <text x={caja.x + caja.ancho / 2} y={caja.y + caja.alto / 2 + 4} textAnchor="middle" fontSize={12} fill="#374151">
                {caja.texto}
              </text>
            </g>
          ))}

          {FILAS.map((fila) => {
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

          {PUESTOS.map((puesto) => {
            const espacio = porCodigo.get(puesto.codigo);
            const elegible = onSeleccionar !== undefined && espacio?.estado === "libre";
            const elegido = espacio !== undefined && espacio.id === seleccionadoId;
            return (
              <rect
                key={puesto.codigo}
                x={puesto.x}
                y={puesto.y}
                width={PUESTO}
                height={PUESTO}
                rx={3}
                fill={
                  esDeVisitante(espacio)
                    ? `url(#${idVisitante})`
                    : espacio
                      ? colorPorEstado[espacio.estado]
                      : COLOR_SIN_CREAR
                }
                stroke={elegido ? "#1e3a8a" : consultado === puesto.codigo ? "#111827" : "none"}
                strokeWidth={elegido ? 3 : 1.5}
                className={elegible ? "cursor-pointer hover:opacity-70" : "cursor-default"}
                onClick={() => tocar(puesto.codigo)}
              >
                <title>{`${puesto.codigo} — ${textoDe(espacio)}`}</title>
              </rect>
            );
          })}
        </svg>
      </div>

      <p className="min-h-5 text-sm text-gray-700">
        {consultado
          ? `Puesto ${consultado}: ${espacioConsultado ? textoDe(espacioConsultado) : "sin crear"}`
          : "Toca un puesto para ver su estado."}
      </p>

      <div className="flex flex-wrap gap-1.5 text-xs">
        {resumen.map((fila) => (
          <span key={fila.letra} className="rounded-full bg-gray-100 px-2 py-0.5 text-gray-700">
            <b>{fila.letra}</b> {fila.libres}/{fila.total}
          </span>
        ))}
      </div>
    </div>
  );
}

// Un item de la leyenda; el color puede ser un degradado.
function Leyenda({ color, texto }: { color: string; texto: string }) {
  return (
    <span className="flex items-center gap-1.5">
      <span className="h-3 w-3 rounded-sm" style={{ background: color }} />
      {texto}
    </span>
  );
}
