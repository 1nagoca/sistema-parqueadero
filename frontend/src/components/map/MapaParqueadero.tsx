import { useEffect, useMemo, useState, type ReactNode } from "react";

import DibujoPlano, { colorPorEstado, COLOR_SIN_CREAR, COLOR_VISITANTE } from "@/components/map/DibujoPlano";
import { ANCHO, BLOQUES, FILAS, PLANO, PUESTOS } from "@/components/map/planoParqueadero";
import type { Espacio, EstadoEspacio } from "@/types/api";

// Muestra de la leyenda: mitad ocupado y mitad visitante.
const MUESTRA_VISITANTE = `linear-gradient(135deg, ${colorPorEstado.ocupado} 50%, ${COLOR_VISITANTE} 50%)`;
const TEXTO_VISITANTE = "Ocupado por visitante";

// Pixeles por unidad del plano: un bloque en grande deja cada puesto entre 24 y 28 px; el plano completo crece hasta 1.25.
const ESCALA_BLOQUE_MINIMA = 24 / 14;
const ESCALA_BLOQUE_MAXIMA = 2;
const ESCALA_PLANO_MAXIMA = 1.25;

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

// Plano del parqueadero con cada puesto pintado segun su estado; en celular se elige un bloque para verlo en grande.
export default function MapaParqueadero({ espacios, onSeleccionar, seleccionadoId, espaciosVisitante }: Props) {
  const [consultado, setConsultado] = useState<string | null>(null);
  // Bloque en grande; null es el plano completo.
  const [bloqueId, setBloqueId] = useState<string | null>(null);
  const pantallaGrande = usePantallaGrande();

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

  // Libres y total de cada bloque, sumando sus letras.
  const resumenBloques = useMemo(
    () =>
      BLOQUES.map((bloque) => {
        const filas = resumen.filter((fila) => bloque.letras.includes(fila.letra));
        return {
          bloque,
          libres: filas.reduce((suma, fila) => suma + fila.libres, 0),
          total: filas.reduce((suma, fila) => suma + fila.total, 0),
        };
      }),
    [resumen],
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
  const bloque = BLOQUES.find((opcion) => opcion.id === bloqueId);
  const interaccion = { onTocar: tocar, textoDe, consultado, seleccionadoId, sePuedeElegir: onSeleccionar !== undefined };

  // Boton de un bloque con sus libres y su total.
  const botonesBloques = resumenBloques.map(({ bloque: opcion, libres, total }) => (
    <BotonBloque
      key={opcion.id}
      activo={bloqueId === opcion.id}
      onClick={() => setBloqueId(opcion.id)}
      tamano={pantallaGrande ? "px-3 text-sm" : "px-2.5 text-xs"}
    >
      <span>{opcion.nombre}</span>
      <span className="tabular-nums">
        {libres}/{total}
      </span>
    </BotonBloque>
  ));

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

      {pantallaGrande ? (
        <div className="flex gap-1.5 overflow-x-auto pb-1">
          <BotonBloque activo={bloqueId === null} onClick={() => setBloqueId(null)} tamano="px-3 text-sm">
            Plano completo
          </BotonBloque>
          {botonesBloques}
        </div>
      ) : (
        <div className="grid grid-cols-[6.5rem_minmax(0,1fr)] gap-3">
          <DibujoPlano
            vista={PLANO}
            porCodigo={porCodigo}
            esDeVisitante={esDeVisitante}
            bloques={{ elegido: bloqueId, onElegir: setBloqueId }}
            className="block w-full rounded-lg border border-gray-200 bg-white"
          />
          <div className="flex flex-col gap-1.5">{botonesBloques}</div>
        </div>
      )}

      {bloque ? (
        <div className="overflow-x-auto rounded-xl border border-gray-200 bg-white">
          <DibujoPlano
            vista={bloque}
            letras={bloque.letras}
            porCodigo={porCodigo}
            esDeVisitante={esDeVisitante}
            interaccion={interaccion}
            className="mx-auto block w-full"
            style={{ minWidth: bloque.ancho * ESCALA_BLOQUE_MINIMA, maxWidth: bloque.ancho * ESCALA_BLOQUE_MAXIMA }}
          />
        </div>
      ) : pantallaGrande ? (
        <div className="rounded-xl border border-gray-200 bg-white">
          <DibujoPlano
            vista={PLANO}
            porCodigo={porCodigo}
            esDeVisitante={esDeVisitante}
            interaccion={interaccion}
            className="mx-auto block w-full"
            style={{ maxWidth: ANCHO * ESCALA_PLANO_MAXIMA }}
          />
        </div>
      ) : (
        <p className="rounded-xl border border-dashed border-gray-300 p-4 text-center text-sm text-gray-500">
          Toca un bloque del plano para ver sus puestos.
        </p>
      )}

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

// Verdadero en pantallas lg o mas anchas.
function usePantallaGrande(): boolean {
  const consulta = "(min-width: 1024px)";
  const [grande, setGrande] = useState(() => window.matchMedia(consulta).matches);
  useEffect(() => {
    const lista = window.matchMedia(consulta);
    const cambiar = () => setGrande(lista.matches);
    lista.addEventListener("change", cambiar);
    return () => lista.removeEventListener("change", cambiar);
  }, []);
  return grande;
}

// Boton del selector de bloques.
function BotonBloque({ activo, onClick, tamano, children }: { activo: boolean; onClick: () => void; tamano: string; children: ReactNode }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`flex items-center justify-between gap-2 whitespace-nowrap rounded-full py-1.5 font-medium ${tamano} ${
        activo ? "bg-emerald-600 text-white" : "bg-gray-100 text-gray-700"
      }`}
    >
      {children}
    </button>
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
