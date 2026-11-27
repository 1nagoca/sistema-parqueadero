import { useCallback, useEffect, useState, type FormEvent } from "react";
import { Link } from "react-router-dom";

import Button from "@/components/common/Button";
import DocumentoVisor from "@/components/verificacion/DocumentoVisor";
import EstadoBadge from "@/components/verificacion/EstadoBadge";
import { useAuth } from "@/context/useAuth";
import { listarMisAccesos } from "@/services/api/accesos";
import { ApiError } from "@/services/api/client";
import { listarMisDocumentos, obtenerUsuarioActual, subirCarnet } from "@/services/api/usuarios";
import {
  listarMisVehiculos,
  registrarMiVehiculo,
  reenviarDocumentosVehiculo,
} from "@/services/api/vehiculos";
import { useActualizacionesZona } from "@/services/realtime/useActualizacionesZona";
import type { Documento, MiAcceso, Usuario, VehiculoConDocumentos } from "@/types/api";

// Estilo comun de los campos y tipos de archivo que se aceptan.
const campo = "min-h-12 w-full rounded-lg border border-gray-300 px-3 focus:border-emerald-500 focus:outline-none";
const ACEPTA_IMAGEN = "image/jpeg,image/png,image/webp";
const ACEPTA_IMAGEN_O_PDF = `${ACEPTA_IMAGEN},application/pdf`;

// Maximo de motos por estudiante (RN-12); debe coincidir con MAX_MOTOS_POR_ESTUDIANTE de identidad.
const MAX_MOTOS = 4;

// Mensaje de error del backend o uno por defecto.
function mensajeDe(err: unknown, porDefecto: string): string {
  return err instanceof ApiError ? err.message : porDefecto;
}

// Panel del estudiante: su verificacion, su carnet y sus vehiculos.
export default function EstudiantePanel() {
  const { usuario, cerrarSesion } = useAuth();
  const [perfil, setPerfil] = useState<Usuario | null>(usuario);
  const [carnet, setCarnet] = useState<Documento[]>([]);
  const [vehiculos, setVehiculos] = useState<VehiculoConDocumentos[]>([]);
  const [error, setError] = useState<string | null>(null);

  // Trae a la vez su perfil, su carnet y sus vehiculos.
  const cargar = useCallback(async () => {
    try {
      const [datosPerfil, datosCarnet, datosVehiculos] = await Promise.all([
        obtenerUsuarioActual(),
        listarMisDocumentos(),
        listarMisVehiculos(),
      ]);
      setPerfil(datosPerfil);
      setCarnet(datosCarnet);
      setVehiculos(datosVehiculos);
      setError(null);
    } catch (err) {
      setError(mensajeDe(err, "No se pudo cargar tu informacion"));
    }
  }, []);

  useEffect(() => {
    cargar();
  }, [cargar]);

  // Puede entrar al parqueadero si el y al menos uno de sus vehiculos estan aprobados.
  const habilitado =
    perfil?.estado_verificacion === "aprobado" && vehiculos.some((v) => v.estado_verificacion === "aprobado");

  return (
    <div className="min-h-screen bg-gray-100 p-4 pb-24 sm:p-6">
      <header className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-gray-900 sm:text-2xl">Mi cuenta</h1>
          {perfil && (
            <p className="text-sm text-gray-500">
              {perfil.nombre_completo}
              {perfil.universidad ? ` · ${perfil.universidad}` : ""}
            </p>
          )}
        </div>
        <button onClick={cerrarSesion} className="text-sm text-gray-500 underline">
          Cerrar sesion
        </button>
      </header>

      <div className="mx-auto max-w-2xl space-y-4">
        {error && <p className="rounded-xl bg-red-100 p-3 text-red-800">{error}</p>}

        <p
          className={`rounded-xl p-3 text-sm ${habilitado ? "bg-emerald-100 text-emerald-800" : "bg-amber-50 text-amber-800"}`}
        >
          {habilitado
            ? "Todo en orden: ya puedes ingresar al parqueadero con tu vehiculo aprobado."
            : "Para ingresar al parqueadero necesitas que tu identidad y al menos un vehiculo sean aprobados por el administrador."}
        </p>

        <TarjetaMiMoto hayVehiculoAprobado={vehiculos.some((v) => v.estado_verificacion === "aprobado")} />

        {perfil && <TarjetaIdentidad perfil={perfil} carnet={carnet} onCambio={cargar} />}
        <TarjetaVehiculos vehiculos={vehiculos} onCambio={cargar} />

        <Link to="/mapa" className="block text-center text-sm text-emerald-700 underline">
          Ver mapa de cupos
        </Link>
      </div>
    </div>
  );
}

// Hora de entrada en Colombia; si no fue hoy, con la fecha corta delante.
function desdeCuando(fechaHora: string): string {
  const zona = { timeZone: "America/Bogota" } as const;
  const entrada = new Date(fechaHora);
  const hora = entrada.toLocaleTimeString("es-CO", { ...zona, hour: "2-digit", minute: "2-digit", hourCycle: "h23" });
  const dia = (fecha: Date) => fecha.toLocaleDateString("en-CA", zona);
  if (dia(entrada) === dia(new Date())) return `desde las ${hora}`;
  const fecha = entrada.toLocaleDateString("es-CO", { ...zona, day: "numeric", month: "short" });
  return `desde el ${fecha}, ${hora}`;
}

// Donde estan sus motos adentro; se refresca con cada entrada o salida que avisa /ws/zonas.
function TarjetaMiMoto({ hayVehiculoAprobado }: { hayVehiculoAprobado: boolean }) {
  const [accesos, setAccesos] = useState<MiAcceso[] | null>(null);
  const [fallo, setFallo] = useState(false);

  // Pide sus motos adentro; si falla, solo esta tarjeta lo avisa.
  const cargar = useCallback(async () => {
    try {
      setAccesos(await listarMisAccesos());
      setFallo(false);
    } catch {
      setFallo(true);
    }
  }, []);

  useEffect(() => {
    cargar();
  }, [cargar]);

  useActualizacionesZona(cargar);

  if (fallo) {
    return (
      <section className="rounded-2xl bg-white p-4 shadow-sm">
        <p className="rounded-lg bg-amber-50 p-2 text-sm text-amber-800">
          No pudimos consultar donde esta tu moto; intenta de nuevo mas tarde.
        </p>
      </section>
    );
  }
  // Mientras carga, o sin motos adentro ni ninguna aprobada, no se muestra nada.
  if (accesos === null || (accesos.length === 0 && !hayVehiculoAprobado)) return null;

  return (
    <section className="space-y-2 rounded-2xl bg-white p-4 shadow-sm">
      {accesos.length === 0 ? (
        <p className="text-sm text-gray-500">Ninguna de tus motos esta en el parqueadero ahora.</p>
      ) : (
        accesos.map((acceso) => (
          <p key={acceso.placa} className="break-words text-gray-900">
            Tu moto <span className="font-semibold">{acceso.placa}</span> esta{" "}
            {acceso.espacio_codigo ? (
              <>
                en el puesto <span className="whitespace-nowrap font-semibold">{acceso.espacio_codigo}</span>
              </>
            ) : (
              "en el parqueadero"
            )}{" "}
            {desdeCuando(acceso.fecha_hora_entrada)}
          </p>
        ))
      )}
    </section>
  );
}

// Estado de su identidad y formulario para subir el carnet.
function TarjetaIdentidad({
  perfil,
  carnet,
  onCambio,
}: {
  perfil: Usuario;
  carnet: Documento[];
  onCambio: () => void;
}) {
  const [archivo, setArchivo] = useState<File | null>(null);
  const [enviando, setEnviando] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Sube el carnet y recarga el panel.
  async function enviar(evento: FormEvent) {
    evento.preventDefault();
    if (!archivo) return;
    setEnviando(true);
    setError(null);
    try {
      await subirCarnet(archivo);
      setArchivo(null);
      onCambio();
    } catch (err) {
      setError(mensajeDe(err, "No se pudo subir el carnet"));
    } finally {
      setEnviando(false);
    }
  }

  const necesitaSubir = perfil.estado_verificacion === "rechazado" || carnet.length === 0;

  return (
    <section className="space-y-3 rounded-2xl bg-white p-4 shadow-sm">
      <div className="flex items-center justify-between">
        <h2 className="font-semibold text-gray-900">Verificacion de estudiante</h2>
        <EstadoBadge estado={perfil.estado_verificacion} />
      </div>
      {perfil.estado_verificacion === "rechazado" && perfil.motivo_rechazo && (
        <p className="rounded-lg bg-red-50 p-2 text-sm text-red-700">Motivo: {perfil.motivo_rechazo}</p>
      )}
      {carnet.map((doc) => (
        <DocumentoVisor key={doc.id} documento={doc} />
      ))}

      {perfil.estado_verificacion !== "aprobado" && necesitaSubir && (
        <form onSubmit={enviar} className="space-y-2">
          <label className="text-sm font-medium text-gray-700" htmlFor="carnet">
            Foto de tu carnet o captura de Divisist donde se vean tus datos y que estudias en la UFPS
          </label>
          <input
            id="carnet"
            type="file"
            required
            accept={ACEPTA_IMAGEN_O_PDF}
            onChange={(e) => setArchivo(e.target.files?.[0] ?? null)}
            className="block w-full text-sm"
          />
          <p className="text-xs text-gray-500">JPG, PNG, WEBP o PDF. Maximo 5 MB.</p>
          {error && <p className="text-sm text-red-600">{error}</p>}
          <Button type="submit" disabled={enviando || !archivo}>
            {enviando ? "Enviando..." : "Enviar para revision"}
          </Button>
        </form>
      )}
      {perfil.estado_verificacion === "pendiente" && carnet.length > 0 && (
        <p className="text-sm text-gray-500">Tu carnet esta en revision por el administrador.</p>
      )}
    </section>
  );
}

// Lista de sus vehiculos y formulario para registrar otro.
function TarjetaVehiculos({ vehiculos, onCambio }: { vehiculos: VehiculoConDocumentos[]; onCambio: () => void }) {
  return (
    <section className="space-y-3 rounded-2xl bg-white p-4 shadow-sm">
      <h2 className="font-semibold text-gray-900">Mis vehiculos</h2>
      {vehiculos.length === 0 && <p className="text-sm text-gray-400">Aun no has registrado ningun vehiculo.</p>}
      {vehiculos.map((vehiculo) => (
        <FilaVehiculo key={vehiculo.id} vehiculo={vehiculo} onCambio={onCambio} />
      ))}
      {vehiculos.length >= MAX_MOTOS ? (
        <p className="text-sm text-gray-400">
          Ya tienes 4 motos registradas, que es el maximo. Si una fue rechazada, corrige sus documentos con Reenviar.
        </p>
      ) : (
        <FormularioVehiculo onCreado={onCambio} />
      )}
    </section>
  );
}

// Un vehiculo con su estado; si fue rechazado, permite reenviar los documentos.
function FilaVehiculo({ vehiculo, onCambio }: { vehiculo: VehiculoConDocumentos; onCambio: () => void }) {
  const [foto, setFoto] = useState<File | null>(null);
  const [tarjeta, setTarjeta] = useState<File | null>(null);
  const [enviando, setEnviando] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Reenvia la foto (de la placa, o del serial si es electrica) y la tarjeta.
  async function reenviar(evento: FormEvent) {
    evento.preventDefault();
    if (!foto || !tarjeta) return;
    setEnviando(true);
    setError(null);
    try {
      await reenviarDocumentosVehiculo(vehiculo.id, foto, tarjeta, vehiculo.es_electrica);
      onCambio();
    } catch (err) {
      setError(mensajeDe(err, "No se pudieron reenviar los documentos"));
    } finally {
      setEnviando(false);
    }
  }

  return (
    <div className="space-y-2 rounded-xl border border-gray-200 p-3">
      <div className="flex items-center justify-between gap-2">
        <div className="min-w-0">
          {vehiculo.es_electrica && <p className="text-xs font-medium text-emerald-700">Moto eléctrica</p>}
          <p className="break-all font-mono text-lg font-semibold text-gray-900">
            {vehiculo.es_electrica ? vehiculo.numero_serie : vehiculo.placa}
          </p>
          <p className="text-sm capitalize text-gray-500">
            {[vehiculo.es_electrica ? null : vehiculo.tipo_vehiculo, vehiculo.marca, vehiculo.color]
              .filter(Boolean)
              .join(" · ")}
          </p>
        </div>
        <EstadoBadge estado={vehiculo.estado_verificacion} />
      </div>
      {vehiculo.estado_verificacion === "rechazado" && (
        <>
          {vehiculo.motivo_rechazo && (
            <p className="rounded-lg bg-red-50 p-2 text-sm text-red-700">Motivo: {vehiculo.motivo_rechazo}</p>
          )}
          <form onSubmit={reenviar} className="space-y-2">
            <p className="text-sm font-medium text-gray-700">Sube de nuevo los documentos corregidos</p>
            <label className="block text-xs text-gray-600">
              {vehiculo.es_electrica ? "Foto del número de serie" : "Foto de la placa"}
              <input
                type="file"
                required
                accept={ACEPTA_IMAGEN}
                onChange={(e) => setFoto(e.target.files?.[0] ?? null)}
                className="block w-full text-sm"
              />
            </label>
            <label className="block text-xs text-gray-600">
              {vehiculo.es_electrica ? "Factura de compra o tarjeta de propiedad" : "Tarjeta de propiedad"}
              <input
                type="file"
                required
                accept={ACEPTA_IMAGEN_O_PDF}
                onChange={(e) => setTarjeta(e.target.files?.[0] ?? null)}
                className="block w-full text-sm"
              />
            </label>
            {error && <p className="text-sm text-red-600">{error}</p>}
            <Button type="submit" disabled={enviando || !foto || !tarjeta}>
              {enviando ? "Enviando..." : "Reenviar"}
            </Button>
          </form>
        </>
      )}
    </div>
  );
}

// Formulario para registrar una moto, normal (placa) o electrica (serial), con sus dos documentos.
function FormularioVehiculo({ onCreado }: { onCreado: () => void }) {
  const [abierto, setAbierto] = useState(false);
  const [electrica, setElectrica] = useState(false);
  const [placa, setPlaca] = useState("");
  const [serie, setSerie] = useState("");
  const [marca, setMarca] = useState("");
  const [modelo, setModelo] = useState("");
  const [color, setColor] = useState("");
  const [foto, setFoto] = useState<File | null>(null);
  const [tarjeta, setTarjeta] = useState<File | null>(null);
  const [enviando, setEnviando] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Al cambiar de tipo se borran la placa, el serial y la foto.
  function cambiarTipo(esElectrica: boolean) {
    setElectrica(esElectrica);
    setPlaca("");
    setSerie("");
    setFoto(null);
    setError(null);
  }

  // Envia la moto y sus documentos; el formato de la placa o el serial lo valida el backend.
  async function enviar(evento: FormEvent) {
    evento.preventDefault();
    if (!foto || !tarjeta) return;
    setEnviando(true);
    setError(null);
    const comunes = { tipo_vehiculo: "moto" as const, marca, modelo, color, tarjeta_propiedad: tarjeta };
    try {
      await registrarMiVehiculo(
        electrica
          ? { ...comunes, es_electrica: true, numero_serie: serie, foto_serial: foto }
          : { ...comunes, placa, foto_placa: foto },
      );
      setElectrica(false);
      setPlaca("");
      setSerie("");
      setMarca("");
      setModelo("");
      setColor("");
      setFoto(null);
      setTarjeta(null);
      setAbierto(false);
      onCreado();
    } catch (err) {
      setError(mensajeDe(err, "No se pudo registrar el vehiculo"));
    } finally {
      setEnviando(false);
    }
  }

  if (!abierto) {
    return (
      <Button variante="secundaria" onClick={() => setAbierto(true)}>
        Registrar vehiculo
      </Button>
    );
  }

  const faltanDatos = !(electrica ? serie.trim() : placa.trim()) || !foto || !tarjeta;
  const opcion = "flex min-h-12 flex-1 items-center gap-2 rounded-lg border px-3 text-sm";

  return (
    <form onSubmit={enviar} className="space-y-3 rounded-xl border border-emerald-200 p-3">
      <fieldset className="space-y-2">
        <legend className="text-sm font-medium text-gray-700">Tipo de moto</legend>
        <div className="flex flex-col gap-2 sm:flex-row">
          <label className={`${opcion} ${electrica ? "border-gray-300" : "border-emerald-500 bg-emerald-50"}`}>
            <input type="radio" name="tipo-moto" checked={!electrica} onChange={() => cambiarTipo(false)} />
            Normal (con placa)
          </label>
          <label className={`${opcion} ${electrica ? "border-emerald-500 bg-emerald-50" : "border-gray-300"}`}>
            <input type="radio" name="tipo-moto" checked={electrica} onChange={() => cambiarTipo(true)} />
            Eléctrica (sin placa)
          </label>
        </div>
        <p className="text-xs text-gray-500">Si tu moto eléctrica tiene placa, regístrala como normal.</p>
      </fieldset>
      <div className="grid gap-3 sm:grid-cols-2">
        {electrica ? (
          <div className="sm:col-span-2">
            <input
              required
              aria-label="Número de serie o VIN"
              placeholder="Número de serie o VIN (ej. EB2024-00871)"
              value={serie}
              maxLength={17}
              onChange={(e) => setSerie(e.target.value.toUpperCase().replace(/\s/g, ""))}
              className={`${campo} font-mono uppercase`}
            />
            <p className="mt-1 text-xs text-gray-500">Está grabado en el chasis o en la lámina técnica.</p>
          </div>
        ) : (
          <input
            required
            placeholder="Placa de la moto (ej. ABC12D o AB1C23D)"
            value={placa}
            maxLength={7}
            onChange={(e) => setPlaca(e.target.value.toUpperCase())}
            className={`${campo} font-mono uppercase`}
          />
        )}
        <input placeholder="Marca" value={marca} onChange={(e) => setMarca(e.target.value)} className={campo} />
        <input placeholder="Modelo" value={modelo} onChange={(e) => setModelo(e.target.value)} className={campo} />
        <input placeholder="Color" value={color} onChange={(e) => setColor(e.target.value)} className={campo} />
      </div>
      <label className="block text-sm text-gray-700">
        {electrica ? "Foto del número de serie" : "Foto de la placa del vehiculo"}
        <input
          key={electrica ? "foto-serial" : "foto-placa"}
          type="file"
          required
          accept={ACEPTA_IMAGEN}
          onChange={(e) => setFoto(e.target.files?.[0] ?? null)}
          className="block w-full text-sm"
        />
      </label>
      <label className="block text-sm text-gray-700">
        {electrica ? "Factura de compra o tarjeta de propiedad" : "Tarjeta de propiedad"}
        <input
          type="file"
          required
          accept={ACEPTA_IMAGEN_O_PDF}
          onChange={(e) => setTarjeta(e.target.files?.[0] ?? null)}
          className="block w-full text-sm"
        />
      </label>
      <p className="text-xs text-gray-500">
        {electrica
          ? "JPG, PNG, WEBP (la factura o tarjeta también PDF). Máximo 5 MB cada uno."
          : "JPG, PNG, WEBP (la tarjeta tambien PDF). Maximo 5 MB cada uno."}
      </p>
      {error && <p className="text-sm text-red-600">{error}</p>}
      <div className="flex gap-2">
        <Button type="submit" disabled={enviando || faltanDatos}>
          {enviando ? "Enviando..." : "Enviar para revision"}
        </Button>
        <Button type="button" variante="secundaria" onClick={() => setAbierto(false)}>
          Cancelar
        </Button>
      </div>
    </form>
  );
}
