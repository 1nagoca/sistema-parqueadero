import { useEffect, useState } from "react";

import Button from "@/components/common/Button";
import MapaParqueadero from "@/components/map/MapaParqueadero";
import PlateReader from "@/components/scanner/PlateReader";
import PlateSearchBar from "@/components/scanner/PlateSearchBar";
import QRScanner from "@/components/scanner/QRScanner";
import { useAuth } from "@/context/AuthContext";
import { ApiError } from "@/services/api/client";
import {
  buscarAccesoActivoPorPlaca,
  listarAccesosActivos,
  registrarEntrada,
  registrarSalida,
} from "@/services/api/accesos";
import { listarEspacios } from "@/services/api/espacios";
import { buscarPorPlaca, crearVehiculo } from "@/services/api/vehiculos";
import type { LecturaPlaca } from "@/services/api/vision";
import { listarZonas } from "@/services/api/zonas";
import { useActualizacionesZona } from "@/services/realtime/useActualizacionesZona";
import type { Acceso, AccesoActivo, Espacio, Vehiculo, Zona } from "@/types/api";

// Lo que se muestra al buscar una placa: nada, cargando, ya esta adentro, registrado o no registrado.
type Resultado =
  | { estado: "vacio" }
  | { estado: "cargando" }
  | { estado: "con_acceso_activo"; vehiculo: Vehiculo; acceso: Acceso }
  | { estado: "vehiculo_registrado"; vehiculo: Vehiculo }
  | { estado: "no_registrado"; placa: string };

// Panel del vigilante: buscar placa (a mano, con foto o con QR) y registrar entradas y salidas.
export default function GuardDashboard() {
  const { usuario, cerrarSesion } = useAuth();
  const [zonas, setZonas] = useState<Zona[]>([]);
  const [zonaId, setZonaId] = useState("");
  const [espaciosZona, setEspaciosZona] = useState<Espacio[]>([]);
  const [espacioId, setEspacioId] = useState("");
  const [accesosActivos, setAccesosActivos] = useState<AccesoActivo[]>([]);
  const [resultado, setResultado] = useState<Resultado>({ estado: "vacio" });
  const [mostrarScanner, setMostrarScanner] = useState(false);
  const [lecturaAlpr, setLecturaAlpr] = useState<LecturaPlaca | null>(null);
  const [mensaje, setMensaje] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [procesando, setProcesando] = useState(false);

  // Al abrir el panel carga las zonas.
  useEffect(() => {
    cargarZonas();
  }, []);

  // Al cambiar de zona carga sus espacios y los vehiculos que estan adentro.
  useEffect(() => {
    if (!zonaId) {
      setEspaciosZona([]);
      setAccesosActivos([]);
      return;
    }
    listarEspacios(zonaId)
      .then(setEspaciosZona)
      .catch(() => setEspaciosZona([]));
    listarAccesosActivos(zonaId)
      .then(setAccesosActivos)
      .catch(() => setAccesosActivos([]));
    setEspacioId("");
  }, [zonaId]);

  // Trae las zonas y elige la primera si no hay ninguna elegida.
  async function cargarZonas() {
    try {
      const datos = await listarZonas();
      setZonas(datos);
      setZonaId((actual) => actual || datos[0]?.id || "");
    } catch {
      setError("No se pudieron cargar las zonas");
    }
  }

  // Refresca cupos, espacios y vehiculos adentro despues de una entrada o salida.
  async function recargarZonaYEspacios() {
    await cargarZonas();
    if (zonaId) {
      listarEspacios(zonaId).then(setEspaciosZona).catch(() => undefined);
      listarAccesosActivos(zonaId).then(setAccesosActivos).catch(() => undefined);
    }
  }

  // Si otro vigilante registra una entrada o salida, el mapa se refresca solo.
  useActualizacionesZona(recargarZonaYEspacios);

  /** `lectura` solo llega cuando la placa la leyo el microservicio de vision; una busqueda
   * manual o por QR la descarta para no marcar el acceso como detectado por ALPR. */
  async function buscar(placa: string, lectura: LecturaPlaca | null = null) {
    setLecturaAlpr(lectura);
    setMostrarScanner(false);
    setMensaje(null);
    setError(null);
    setResultado({ estado: "cargando" });
    try {
      // Primero mira si ya esta adentro (ofrece salida); si no, si esta registrado (ofrece entrada).
      const accesoActivo = await buscarAccesoActivoPorPlaca(placa);
      if (accesoActivo) {
        const vehiculo = await buscarPorPlaca(placa);
        setResultado({ estado: "con_acceso_activo", vehiculo, acceso: accesoActivo });
        return;
      }
      try {
        const vehiculo = await buscarPorPlaca(placa);
        setResultado({ estado: "vehiculo_registrado", vehiculo });
      } catch (err) {
        if (err instanceof ApiError && err.status === 404) {
          setResultado({ estado: "no_registrado", placa });
        } else {
          throw err;
        }
      }
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Error buscando la placa");
      setResultado({ estado: "vacio" });
    }
  }

  // Marca el acceso como leido por vision si la placa vino de una foto.
  function camposAlpr() {
    return lecturaAlpr
      ? { placa_detectada_por_alpr: true, confianza_alpr: lecturaAlpr.confianza }
      : {};
  }

  // Entrada de un vehiculo registrado.
  async function confirmarEntradaNormal(vehiculoId: string) {
    await conCargando(() =>
      registrarEntrada({
        vehiculo_id: vehiculoId,
        zona_id: zonaId,
        espacio_id: espacioId,
        tipo_acceso: "normal",
        ...camposAlpr(),
      }),
    );
  }

  // Entrada de visitante: la autoriza el vigilante de la sesion con una justificacion.
  async function confirmarEntradaVisitante(vehiculoId: string, justificacion: string) {
    if (!usuario) return;
    await conCargando(() =>
      registrarEntrada({
        vehiculo_id: vehiculoId,
        zona_id: zonaId,
        espacio_id: espacioId,
        tipo_acceso: "visitante",
        autorizado_por_id: usuario.id,
        justificacion,
        ...camposAlpr(),
      }),
    );
  }

  // Salida de un vehiculo que esta adentro.
  async function confirmarSalida(accesoId: string) {
    await conCargando(() => registrarSalida(accesoId));
  }

  // Ejecuta la accion mostrando que esta procesando; al terminar limpia y refresca.
  async function conCargando(accion: () => Promise<unknown>) {
    if (!zonaId && resultado.estado !== "con_acceso_activo") {
      setError("Selecciona una zona");
      return;
    }
    setProcesando(true);
    setError(null);
    try {
      await accion();
      setMensaje("Listo");
      setResultado({ estado: "vacio" });
      setLecturaAlpr(null);
      setEspacioId("");
      recargarZonaYEspacios();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "No se pudo completar la operacion");
    } finally {
      setProcesando(false);
    }
  }

  // La zona elegida y si se quedo sin cupos.
  const zonaSeleccionada = zonas.find((z) => z.id === zonaId);
  const sinCupos = zonaSeleccionada !== undefined && zonaSeleccionada.cupos_disponibles <= 0;
  // El puesto elegido, solo si sigue libre (otro vigilante pudo ocuparlo).
  const puestoElegido = espaciosZona.find((espacio) => espacio.id === espacioId && espacio.estado === "libre");

  return (
    <div className="min-h-screen bg-gray-100 p-4 pb-24 sm:p-6">
      <header className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-gray-900 sm:text-2xl">Panel de Vigilancia</h1>
          {usuario && <p className="text-sm text-gray-500">{usuario.nombre_completo}</p>}
        </div>
        <button onClick={cerrarSesion} className="text-sm text-gray-500 underline">
          Cerrar sesion
        </button>
      </header>

      <section className="mb-4 rounded-2xl bg-white p-4 shadow-sm">
        <label className="mb-1 block text-sm font-medium text-gray-700" htmlFor="zona">
          Zona
        </label>
        <select
          id="zona"
          value={zonaId}
          onChange={(evento) => setZonaId(evento.target.value)}
          className="min-h-12 w-full rounded-lg border border-gray-300 px-3"
        >
          {zonas.map((zona) => (
            <option key={zona.id} value={zona.id}>
              {zona.nombre} — {zona.cupos_disponibles}/{zona.capacidad_total} cupos
            </option>
          ))}
        </select>
        {sinCupos && <p className="mt-1 text-sm text-red-600">Esta zona no tiene cupos disponibles.</p>}

        <p className="mt-3 text-sm font-medium text-gray-700">
          {puestoElegido ? (
            <>
              Puesto elegido: <span className="text-blue-900">{puestoElegido.codigo}</span>
            </>
          ) : (
            "Toca un puesto libre (verde) en el mapa para la entrada."
          )}
        </p>
        <div className="mt-2">
          <MapaParqueadero
            espacios={espaciosZona}
            seleccionadoId={puestoElegido?.id}
            onSeleccionar={(espacio) => setEspacioId(espacio.id)}
          />
        </div>
      </section>

      <section className="mb-4 space-y-3 rounded-2xl bg-white p-4 shadow-sm">
        <PlateSearchBar onBuscar={buscar} buscando={resultado.estado === "cargando"} />
        <PlateReader onDetectada={(lectura) => buscar(lectura.placa, lectura)} />
        {lecturaAlpr && (
          <p className="text-sm text-gray-600">
            Placa leida por camara: <span className="font-semibold">{lecturaAlpr.placa}</span> (confianza{" "}
            {Math.round(lecturaAlpr.confianza * 100)}%)
          </p>
        )}
        <Button
          type="button"
          variante="secundaria"
          className="w-full"
          onClick={() => setMostrarScanner((valor) => !valor)}
        >
          {mostrarScanner ? "Cerrar camara" : "Escanear QR"}
        </Button>
        <QRScanner activo={mostrarScanner} onDetectado={(placa) => buscar(placa)} />
      </section>

      {mensaje && <p className="mb-4 rounded-xl bg-emerald-100 p-3 text-emerald-800">{mensaje}</p>}
      {error && <p className="mb-4 rounded-xl bg-red-100 p-3 text-red-800">{error}</p>}

      <section className="mb-4 rounded-2xl bg-white p-4 shadow-sm">
        <h2 className="mb-3 font-semibold text-gray-900">
          Vehiculos adentro {zonaSeleccionada && `— ${zonaSeleccionada.nombre}`}
        </h2>
        {accesosActivos.length === 0 ? (
          <p className="text-sm text-gray-400">No hay vehiculos registrados en esta zona ahora mismo.</p>
        ) : (
          <ul className="divide-y divide-gray-100">
            {accesosActivos.map((acceso) => (
              <li key={acceso.id} className="flex items-center justify-between gap-3 py-3">
                <div>
                  <p className="font-medium text-gray-900">
                    {acceso.placa}
                    {acceso.espacio_codigo && (
                      <span className="ml-2 text-sm font-normal text-gray-500">({acceso.espacio_codigo})</span>
                    )}
                  </p>
                  <p className="text-xs text-gray-500">
                    Desde {new Date(acceso.fecha_hora_entrada).toLocaleString("es-CO")}
                  </p>
                </div>
                <Button
                  variante="peligro"
                  disabled={procesando}
                  className="min-h-10 px-4 py-2 text-sm"
                  onClick={() => confirmarSalida(acceso.id)}
                >
                  Registrar salida
                </Button>
              </li>
            ))}
          </ul>
        )}
      </section>

      <ResultadoPanel
        resultado={resultado}
        procesando={procesando}
        sinCupos={sinCupos}
        puesto={puestoElegido?.codigo ?? null}
        onEntradaNormal={confirmarEntradaNormal}
        onSalida={confirmarSalida}
        onRegistrarVehiculoVisitante={async (placa, justificacion) => {
          // Visitante no registrado: primero crea el vehiculo y luego registra la entrada.
          if (!usuario) return;
          setProcesando(true);
          setError(null);
          try {
            const vehiculo = await crearVehiculo({
              placa,
              tipo_vehiculo: "moto",
              es_visitante: true,
            });
            await confirmarEntradaVisitante(vehiculo.id, justificacion);
          } catch (err) {
            setError(err instanceof ApiError ? err.message : "No se pudo registrar el vehiculo");
            setProcesando(false);
          }
        }}
      />
    </div>
  );
}

// Lo que recibe ResultadoPanel desde el panel.
interface ResultadoPanelProps {
  resultado: Resultado;
  procesando: boolean;
  sinCupos: boolean;
  // Codigo del puesto elegido en el mapa (RN-06: sin puesto no hay entrada).
  puesto: string | null;
  onEntradaNormal: (vehiculoId: string) => void;
  onSalida: (accesoId: string) => void;
  onRegistrarVehiculoVisitante: (placa: string, justificacion: string) => void;
}

// Muestra el resultado de la busqueda con el boton que corresponde (entrada, salida o visitante).
function ResultadoPanel({
  resultado,
  procesando,
  sinCupos,
  puesto,
  onEntradaNormal,
  onSalida,
  onRegistrarVehiculoVisitante,
}: ResultadoPanelProps) {
  if (resultado.estado === "vacio") {
    return (
      <p className="rounded-2xl bg-white p-6 text-center text-gray-400 shadow-sm">
        Busca una placa, lee una con foto o escanea un QR para comenzar.
      </p>
    );
  }

  if (resultado.estado === "cargando") {
    return <p className="rounded-2xl bg-white p-6 text-center text-gray-400 shadow-sm">Buscando...</p>;
  }

  if (resultado.estado === "con_acceso_activo") {
    return (
      <div className="rounded-2xl bg-white p-4 shadow-sm">
        <p className="text-lg font-semibold text-gray-900">{resultado.vehiculo.placa}</p>
        <p className="text-sm text-gray-500">
          Dentro desde {new Date(resultado.acceso.fecha_hora_entrada).toLocaleString("es-CO")}
        </p>
        <Button
          variante="peligro"
          className="mt-4 w-full"
          disabled={procesando}
          onClick={() => onSalida(resultado.acceso.id)}
        >
          Registrar salida
        </Button>
      </div>
    );
  }

  if (resultado.estado === "vehiculo_registrado") {
    return (
      <div className="rounded-2xl bg-white p-4 shadow-sm">
        <p className="text-lg font-semibold text-gray-900">{resultado.vehiculo.placa}</p>
        <p className="text-sm text-gray-500">{resultado.vehiculo.tipo_vehiculo}</p>
        <Button
          className="mt-4 w-full"
          disabled={procesando || sinCupos || !puesto}
          onClick={() => onEntradaNormal(resultado.vehiculo.id)}
        >
          {puesto ? `Registrar entrada en ${puesto}` : "Elige un puesto en el mapa"}
        </Button>
      </div>
    );
  }

  return (
    <FormularioVisitante
      placa={resultado.placa}
      procesando={procesando}
      sinCupos={sinCupos}
      puesto={puesto}
      onConfirmar={onRegistrarVehiculoVisitante}
    />
  );
}

// Formulario para dejar entrar como visitante un vehiculo no registrado.
function FormularioVisitante({
  placa,
  procesando,
  sinCupos,
  puesto,
  onConfirmar,
}: {
  placa: string;
  procesando: boolean;
  sinCupos: boolean;
  puesto: string | null;
  onConfirmar: (placa: string, justificacion: string) => void;
}) {
  const [justificacion, setJustificacion] = useState("");

  return (
    <div className="space-y-3 rounded-2xl bg-white p-4 shadow-sm">
      <p className="text-lg font-semibold text-gray-900">{placa}</p>
      <p className="text-sm text-amber-600">Moto no registrada — requiere autorizacion de visitante (RN-03).</p>

      <textarea
        value={justificacion}
        onChange={(evento) => setJustificacion(evento.target.value)}
        placeholder="Justificacion del ingreso (obligatoria)"
        className="min-h-20 w-full rounded-lg border border-gray-300 px-3 py-2"
      />

      <Button
        className="w-full"
        disabled={procesando || sinCupos || !puesto || !justificacion.trim()}
        onClick={() => onConfirmar(placa, justificacion.trim())}
      >
        {puesto ? `Autorizar entrada de visitante en ${puesto}` : "Elige un puesto en el mapa"}
      </Button>
    </div>
  );
}
