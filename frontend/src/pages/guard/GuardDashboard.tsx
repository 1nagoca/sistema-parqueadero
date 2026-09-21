import { useEffect, useState } from "react";

import Button from "@/components/common/Button";
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
import { listarZonas } from "@/services/api/zonas";
import type { Acceso, AccesoActivo, Espacio, TipoVehiculo, Vehiculo, Zona } from "@/types/api";

type Resultado =
  | { estado: "vacio" }
  | { estado: "cargando" }
  | { estado: "con_acceso_activo"; vehiculo: Vehiculo; acceso: Acceso }
  | { estado: "vehiculo_registrado"; vehiculo: Vehiculo }
  | { estado: "no_registrado"; placa: string };

export default function GuardDashboard() {
  const { usuario, cerrarSesion } = useAuth();
  const [zonas, setZonas] = useState<Zona[]>([]);
  const [zonaId, setZonaId] = useState("");
  const [espaciosZona, setEspaciosZona] = useState<Espacio[]>([]);
  const [espacioId, setEspacioId] = useState("");
  const [accesosActivos, setAccesosActivos] = useState<AccesoActivo[]>([]);
  const [resultado, setResultado] = useState<Resultado>({ estado: "vacio" });
  const [mostrarScanner, setMostrarScanner] = useState(false);
  const [mensaje, setMensaje] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [procesando, setProcesando] = useState(false);

  useEffect(() => {
    cargarZonas();
  }, []);

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

  async function cargarZonas() {
    try {
      const datos = await listarZonas();
      setZonas(datos);
      setZonaId((actual) => actual || datos[0]?.id || "");
    } catch {
      setError("No se pudieron cargar las zonas");
    }
  }

  async function recargarZonaYEspacios() {
    await cargarZonas();
    if (zonaId) {
      listarEspacios(zonaId).then(setEspaciosZona).catch(() => undefined);
      listarAccesosActivos(zonaId).then(setAccesosActivos).catch(() => undefined);
    }
  }

  async function buscar(placa: string) {
    setMostrarScanner(false);
    setMensaje(null);
    setError(null);
    setResultado({ estado: "cargando" });
    try {
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

  async function confirmarEntradaNormal(vehiculoId: string) {
    await conCargando(() =>
      registrarEntrada({
        vehiculo_id: vehiculoId,
        zona_id: zonaId,
        espacio_id: espacioId || null,
        tipo_acceso: "normal",
      }),
    );
  }

  async function confirmarEntradaVisitante(vehiculoId: string, justificacion: string) {
    if (!usuario) return;
    await conCargando(() =>
      registrarEntrada({
        vehiculo_id: vehiculoId,
        zona_id: zonaId,
        espacio_id: espacioId || null,
        tipo_acceso: "visitante",
        autorizado_por_id: usuario.id,
        justificacion,
      }),
    );
  }

  async function confirmarSalida(accesoId: string) {
    await conCargando(() => registrarSalida(accesoId));
  }

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
      setEspacioId("");
      recargarZonaYEspacios();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "No se pudo completar la operacion");
    } finally {
      setProcesando(false);
    }
  }

  const zonaSeleccionada = zonas.find((z) => z.id === zonaId);
  const sinCupos = zonaSeleccionada !== undefined && zonaSeleccionada.cupos_disponibles <= 0;

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

        {espaciosZona.length > 0 && (
          <div className="mt-3">
            <label className="mb-1 block text-sm font-medium text-gray-700" htmlFor="espacio">
              Espacio (opcional)
            </label>
            <select
              id="espacio"
              value={espacioId}
              onChange={(evento) => setEspacioId(evento.target.value)}
              className="min-h-12 w-full rounded-lg border border-gray-300 px-3"
            >
              <option value="">Sin espacio especifico (solo contador de la zona)</option>
              {espaciosZona
                .filter((espacio) => espacio.estado === "libre")
                .map((espacio) => (
                  <option key={espacio.id} value={espacio.id}>
                    {espacio.codigo}
                  </option>
                ))}
            </select>
          </div>
        )}
      </section>

      <section className="mb-4 space-y-3 rounded-2xl bg-white p-4 shadow-sm">
        <PlateSearchBar onBuscar={buscar} buscando={resultado.estado === "cargando"} />
        <Button
          type="button"
          variante="secundaria"
          className="w-full"
          onClick={() => setMostrarScanner((valor) => !valor)}
        >
          {mostrarScanner ? "Cerrar camara" : "Escanear QR"}
        </Button>
        <QRScanner activo={mostrarScanner} onDetectado={buscar} />
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
        onEntradaNormal={confirmarEntradaNormal}
        onSalida={confirmarSalida}
        onRegistrarVehiculoVisitante={async (placa, tipoVehiculo, justificacion) => {
          if (!usuario) return;
          setProcesando(true);
          setError(null);
          try {
            const vehiculo = await crearVehiculo({
              placa,
              tipo_vehiculo: tipoVehiculo,
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

interface ResultadoPanelProps {
  resultado: Resultado;
  procesando: boolean;
  sinCupos: boolean;
  onEntradaNormal: (vehiculoId: string) => void;
  onSalida: (accesoId: string) => void;
  onRegistrarVehiculoVisitante: (placa: string, tipo: TipoVehiculo, justificacion: string) => void;
}

function ResultadoPanel({
  resultado,
  procesando,
  sinCupos,
  onEntradaNormal,
  onSalida,
  onRegistrarVehiculoVisitante,
}: ResultadoPanelProps) {
  if (resultado.estado === "vacio") {
    return (
      <p className="rounded-2xl bg-white p-6 text-center text-gray-400 shadow-sm">
        Busca una placa o escanea un QR para comenzar.
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
          disabled={procesando || sinCupos}
          onClick={() => onEntradaNormal(resultado.vehiculo.id)}
        >
          Registrar entrada
        </Button>
      </div>
    );
  }

  return (
    <FormularioVisitante
      placa={resultado.placa}
      procesando={procesando}
      sinCupos={sinCupos}
      onConfirmar={onRegistrarVehiculoVisitante}
    />
  );
}

function FormularioVisitante({
  placa,
  procesando,
  sinCupos,
  onConfirmar,
}: {
  placa: string;
  procesando: boolean;
  sinCupos: boolean;
  onConfirmar: (placa: string, tipo: TipoVehiculo, justificacion: string) => void;
}) {
  const [tipo, setTipo] = useState<TipoVehiculo>("carro");
  const [justificacion, setJustificacion] = useState("");

  return (
    <div className="space-y-3 rounded-2xl bg-white p-4 shadow-sm">
      <p className="text-lg font-semibold text-gray-900">{placa}</p>
      <p className="text-sm text-amber-600">Vehiculo no registrado — requiere autorizacion de visitante (RN-03).</p>

      <select
        value={tipo}
        onChange={(evento) => setTipo(evento.target.value as TipoVehiculo)}
        className="min-h-12 w-full rounded-lg border border-gray-300 px-3"
      >
        <option value="carro">Carro</option>
        <option value="moto">Moto</option>
        <option value="bicicleta">Bicicleta</option>
        <option value="otro">Otro</option>
      </select>

      <textarea
        value={justificacion}
        onChange={(evento) => setJustificacion(evento.target.value)}
        placeholder="Justificacion del ingreso (obligatoria)"
        className="min-h-20 w-full rounded-lg border border-gray-300 px-3 py-2"
      />

      <Button
        className="w-full"
        disabled={procesando || sinCupos || !justificacion.trim()}
        onClick={() => onConfirmar(placa, tipo, justificacion.trim())}
      >
        Autorizar entrada de visitante
      </Button>
    </div>
  );
}
