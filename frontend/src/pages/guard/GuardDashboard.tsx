import { useEffect, useMemo, useRef, useState } from "react";

import Button from "@/components/common/Button";
import MapaParqueadero from "@/components/map/MapaParqueadero";
import PlateReader from "@/components/scanner/PlateReader";
import PlateSearchBar, { type ModoBusqueda } from "@/components/scanner/PlateSearchBar";
import QRScanner from "@/components/scanner/QRScanner";
import CarnetPropietario from "@/components/verificacion/CarnetPropietario";
import { useAuth } from "@/context/useAuth";
import { ApiError } from "@/services/api/client";
import {
  buscarAccesoActivo,
  listarAccesosActivos,
  registrarEntrada,
  registrarSalida,
} from "@/services/api/accesos";
import { listarEspacios } from "@/services/api/espacios";
import { buscarPorPlaca, buscarPorSerie, crearVehiculo } from "@/services/api/vehiculos";
import type { LecturaPlaca } from "@/services/api/vision";
import { listarZonas } from "@/services/api/zonas";
import { useActualizacionesZona } from "@/services/realtime/useActualizacionesZona";
import type { Acceso, AccesoActivo, Espacio, MotoBuscada, Vehiculo, VehiculoConPlaca, Zona } from "@/types/api";

// Lo que se muestra al buscar una moto: nada, cargando, ya esta adentro, registrada, visitante que necesita autorizacion, no registrada o electrica no registrada.
type Resultado =
  | { estado: "vacio" }
  | { estado: "cargando" }
  | { estado: "con_acceso_activo"; moto: MotoBuscada; acceso: Acceso }
  | { estado: "vehiculo_registrado"; moto: MotoBuscada; vehiculo: Vehiculo }
  | { estado: "visitante_sin_autorizacion"; vehiculo: VehiculoConPlaca }
  | { estado: "no_registrado"; placa: string }
  | { estado: "electrica_no_registrada"; numeroSerie: string };

// Solo una moto con placa puede seguir como visitante (la electrica es de un estudiante).
function tienePlaca(vehiculo: Vehiculo): vehiculo is VehiculoConPlaca {
  return vehiculo.placa !== null;
}

// Panel del vigilante: buscar placa (a mano, con foto o con QR) y registrar entradas y salidas.
export default function GuardDashboard() {
  const { usuario, cerrarSesion } = useAuth();
  const [zonas, setZonas] = useState<Zona[]>([]);
  const [zonaId, setZonaId] = useState("");
  const [espaciosZona, setEspaciosZona] = useState<Espacio[]>([]);
  const [espacioId, setEspacioId] = useState("");
  const [accesosActivos, setAccesosActivos] = useState<AccesoActivo[]>([]);
  const [resultado, setResultado] = useState<Resultado>({ estado: "vacio" });
  // Que busca el vigilante: placas (con foto y QR) o el serial de una moto electrica.
  const [modo, setModo] = useState<ModoBusqueda>("placa");
  // Contenedor del resultado, para bajar hasta el carnet al verificar una salida.
  const resultadoRef = useRef<HTMLDivElement>(null);
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

  // Puestos ocupados por un visitante, para pintarlos distinto en el mapa.
  const espaciosVisitante = useMemo(
    () =>
      new Set(
        accesosActivos
          .filter((acceso) => acceso.tipo_acceso === "visitante" && acceso.espacio_id)
          .map((acceso) => acceso.espacio_id as string),
      ),
    [accesosActivos],
  );

  /** `lectura` solo llega cuando la placa la leyo el microservicio de vision; una busqueda
   * manual o por QR la descarta para no marcar el acceso como detectado por ALPR. */
  async function buscar(moto: MotoBuscada, lectura: LecturaPlaca | null = null) {
    setLecturaAlpr(lectura);
    setMostrarScanner(false);
    setMensaje(null);
    setError(null);
    setResultado({ estado: "cargando" });
    try {
      // Primero mira si ya esta adentro (ofrece salida); si no, si esta registrada (ofrece entrada).
      const accesoActivo = await buscarAccesoActivo(moto);
      if (accesoActivo) {
        // La salida no consulta a identidad para que funcione aunque identidad este caida.
        // El serial guardado (con sus guiones), aunque se haya buscado sin ellos.
        const guardada = accesoActivo.numero_serie ? { numeroSerie: accesoActivo.numero_serie } : moto;
        setResultado({ estado: "con_acceso_activo", moto: guardada, acceso: accesoActivo });
        return;
      }
      try {
        if ("placa" in moto) {
          const vehiculo = await buscarPorPlaca(moto.placa);
          setResultado({ estado: "vehiculo_registrado", moto, vehiculo });
        } else {
          const vehiculo = await buscarPorSerie(moto.numeroSerie);
          // Se muestra el serial como quedo en identidad (con sus guiones).
          setResultado({
            estado: "vehiculo_registrado",
            moto: { numeroSerie: vehiculo.numero_serie ?? moto.numeroSerie },
            vehiculo,
          });
        }
      } catch (err) {
        if (err instanceof ApiError && err.status === 404) {
          setResultado(
            "placa" in moto
              ? { estado: "no_registrado", placa: moto.placa }
              : { estado: "electrica_no_registrada", numeroSerie: moto.numeroSerie },
          );
        } else {
          throw err;
        }
      }
    } catch (err) {
      const porDefecto = "placa" in moto ? "Error buscando la placa" : "Error buscando el número de serie";
      setError(err instanceof ApiError ? err.message : porDefecto);
      setResultado({ estado: "vacio" });
    }
  }

  // Al cambiar de modo se cierra la camara del QR (solo existe en el modo placa).
  function cambiarModo(nuevo: ModoBusqueda) {
    setModo(nuevo);
    setMostrarScanner(false);
  }

  // Marca el acceso como leido por vision si la placa vino de una foto.
  function camposAlpr() {
    return lecturaAlpr
      ? { placa_detectada_por_alpr: true, confianza_alpr: lecturaAlpr.confianza }
      : {};
  }

  // Entrada de un vehiculo registrado; si es de visitante y accesos responde 409 (RN-03), pide nueva autorizacion.
  async function confirmarEntradaNormal(vehiculoId: string) {
    const fallo = await conCargando(() =>
      registrarEntrada({
        vehiculo_id: vehiculoId,
        zona_id: zonaId,
        espacio_id: espacioId,
        tipo_acceso: "normal",
        ...camposAlpr(),
      }),
    );
    if (
      fallo instanceof ApiError &&
      fallo.status === 409 &&
      resultado.estado === "vehiculo_registrado" &&
      resultado.vehiculo.es_visitante &&
      tienePlaca(resultado.vehiculo)
    ) {
      setResultado({ estado: "visitante_sin_autorizacion", vehiculo: resultado.vehiculo });
    }
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

  // Desde la lista abre la misma verificacion que la busqueda (carnet del dueno, RN-09) y baja hasta ella.
  async function verificarSalida(acceso: AccesoActivo) {
    const electrica = acceso.es_electrica && acceso.numero_serie !== null;
    cambiarModo(electrica ? "serie" : "placa");
    await buscar(electrica ? { numeroSerie: acceso.numero_serie ?? "" } : { placa: acceso.placa ?? "" });
    resultadoRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  // Ejecuta la accion mostrando que esta procesando; al terminar limpia y refresca. Devuelve el error si fallo.
  async function conCargando(accion: () => Promise<unknown>): Promise<unknown> {
    if (!zonaId && resultado.estado !== "con_acceso_activo") {
      setError("Selecciona una zona");
      return null;
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
      return null;
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "No se pudo completar la operacion");
      return err;
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
            espaciosVisitante={espaciosVisitante}
          />
        </div>
      </section>

      <section className="mb-4 space-y-3 rounded-2xl bg-white p-4 shadow-sm">
        <PlateSearchBar
          modo={modo}
          onCambiarModo={cambiarModo}
          onBuscar={(moto) => buscar(moto)}
          buscando={resultado.estado === "cargando"}
        />
        {modo === "placa" && (
          <>
            <PlateReader onDetectada={(lectura) => buscar({ placa: lectura.placa }, lectura)} />
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
            <QRScanner activo={mostrarScanner} onDetectado={(placa) => buscar({ placa })} />
          </>
        )}
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
                <div className="min-w-0">
                  <p className="break-words font-medium text-gray-900">
                    {acceso.es_electrica ? (
                      <>
                        <span className="block text-xs font-medium text-emerald-700">Moto eléctrica</span>
                        <span className="whitespace-nowrap font-mono">{acceso.numero_serie}</span>
                      </>
                    ) : (
                      acceso.placa
                    )}
                    {acceso.espacio_codigo && (
                      <span className="ml-2 whitespace-nowrap text-sm font-normal text-gray-500">({acceso.espacio_codigo})</span>
                    )}
                    {acceso.tipo_acceso === "visitante" && (
                      <span className="ml-2 rounded-full bg-violet-100 px-2 py-0.5 text-xs font-medium text-violet-800">
                        Visitante
                      </span>
                    )}
                  </p>
                  <p className="text-xs text-gray-500">
                    Desde {new Date(acceso.fecha_hora_entrada).toLocaleString("es-CO")}
                  </p>
                </div>
                <Button
                  variante="secundaria"
                  disabled={procesando}
                  className="min-h-10 px-4 py-2 text-sm"
                  onClick={() => verificarSalida(acceso)}
                >
                  Verificar salida
                </Button>
              </li>
            ))}
          </ul>
        )}
      </section>

      <div ref={resultadoRef} className="scroll-mt-4">
        <ResultadoPanel
          resultado={resultado}
          procesando={procesando}
          sinCupos={sinCupos}
          puesto={puestoElegido?.codigo ?? null}
          onEntradaNormal={confirmarEntradaNormal}
          onSalida={confirmarSalida}
          onAutorizarVisitante={confirmarEntradaVisitante}
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
  onAutorizarVisitante: (vehiculoId: string, justificacion: string) => void;
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
  onAutorizarVisitante,
  onRegistrarVehiculoVisitante,
}: ResultadoPanelProps) {
  if (resultado.estado === "vacio") {
    return (
      <p className="rounded-2xl bg-white p-6 text-center text-gray-400 shadow-sm">
        Busca una placa o el número de serie de una moto eléctrica, lee una placa con foto o escanea un QR para
        comenzar.
      </p>
    );
  }

  if (resultado.estado === "cargando") {
    return <p className="rounded-2xl bg-white p-6 text-center text-gray-400 shadow-sm">Buscando...</p>;
  }

  if (resultado.estado === "con_acceso_activo") {
    return (
      <div className="rounded-2xl bg-white p-4 shadow-sm">
        <NombreMoto moto={resultado.moto} />
        <p className="text-sm text-gray-500">
          Dentro desde {new Date(resultado.acceso.fecha_hora_entrada).toLocaleString("es-CO")}
        </p>
        {resultado.acceso.tipo_acceso !== "visitante" && <CarnetPropietario moto={resultado.moto} />}
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
        <NombreMoto moto={resultado.moto} />
        {!resultado.vehiculo.es_electrica && (
          <p className="text-sm text-gray-500">{resultado.vehiculo.tipo_vehiculo}</p>
        )}
        {!resultado.vehiculo.es_visitante && <CarnetPropietario moto={resultado.moto} />}
        <Button
          className="mt-4 w-full"
          disabled={procesando || sinCupos || !puesto}
          onClick={() => onEntradaNormal(resultado.vehiculo.id)}
        >
          {puesto ? `Registrar entrada en ${puesto}` : "Elige un puesto en el mapa"}
        </Button>
        {resultado.vehiculo.es_visitante && (
          <p className="mt-2 text-sm text-gray-400">
            Visitante: entra sin nueva autorizacion solo si salio hace menos de 1 hora
          </p>
        )}
      </div>
    );
  }

  if (resultado.estado === "visitante_sin_autorizacion") {
    return (
      <FormularioVisitante
        placa={resultado.vehiculo.placa}
        aviso="Visitante: salio hace mas de 1 hora o no tiene una autorizacion previa — requiere nueva autorizacion (RN-03)."
        procesando={procesando}
        sinCupos={sinCupos}
        puesto={puesto}
        onConfirmar={(_placa, justificacion) => onAutorizarVisitante(resultado.vehiculo.id, justificacion)}
      />
    );
  }

  if (resultado.estado === "electrica_no_registrada") {
    return (
      <div className="rounded-2xl bg-white p-4 shadow-sm">
        <NombreMoto moto={{ numeroSerie: resultado.numeroSerie }} />
        <p className="mt-2 text-sm text-amber-600">
          Moto eléctrica no registrada: la registra el estudiante desde su panel y la aprueba el administrador
        </p>
      </div>
    );
  }

  return (
    <FormularioVisitante
      placa={resultado.placa}
      aviso="Moto no registrada — requiere autorizacion de visitante (RN-03)."
      procesando={procesando}
      sinCupos={sinCupos}
      puesto={puesto}
      onConfirmar={onRegistrarVehiculoVisitante}
    />
  );
}

// La placa como hoy, o «Moto eléctrica» y el numero de serie.
function NombreMoto({ moto }: { moto: MotoBuscada }) {
  if ("placa" in moto) {
    return <p className="text-lg font-semibold text-gray-900">{moto.placa}</p>;
  }
  return (
    <>
      <p className="text-xs font-medium text-emerald-700">Moto eléctrica</p>
      <p className="break-all font-mono text-lg font-semibold text-gray-900">{moto.numeroSerie}</p>
    </>
  );
}

// Formulario para dejar entrar como visitante un vehiculo no registrado.
function FormularioVisitante({
  placa,
  aviso,
  procesando,
  sinCupos,
  puesto,
  onConfirmar,
}: {
  placa: string;
  aviso: string;
  procesando: boolean;
  sinCupos: boolean;
  puesto: string | null;
  onConfirmar: (placa: string, justificacion: string) => void;
}) {
  const [justificacion, setJustificacion] = useState("");

  return (
    <div className="space-y-3 rounded-2xl bg-white p-4 shadow-sm">
      <p className="text-lg font-semibold text-gray-900">{placa}</p>
      <p className="text-sm text-amber-600">{aviso}</p>

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
