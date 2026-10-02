import { useCallback, useEffect, useState, type FormEvent } from "react";
import { Link } from "react-router-dom";

import Button from "@/components/common/Button";
import DocumentoVisor from "@/components/verificacion/DocumentoVisor";
import EstadoBadge from "@/components/verificacion/EstadoBadge";
import { useAuth } from "@/context/AuthContext";
import { ApiError } from "@/services/api/client";
import { listarMisDocumentos, obtenerUsuarioActual, subirCarnet } from "@/services/api/usuarios";
import {
  listarMisVehiculos,
  registrarMiVehiculo,
  reenviarDocumentosVehiculo,
} from "@/services/api/vehiculos";
import type { Documento, TipoVehiculo, Usuario, VehiculoConDocumentos } from "@/types/api";

const campo = "min-h-12 w-full rounded-lg border border-gray-300 px-3 focus:border-emerald-500 focus:outline-none";
const ACEPTA_IMAGEN = "image/jpeg,image/png,image/webp";
const ACEPTA_IMAGEN_O_PDF = `${ACEPTA_IMAGEN},application/pdf`;

function mensajeDe(err: unknown, porDefecto: string): string {
  return err instanceof ApiError ? err.message : porDefecto;
}

export default function EstudiantePanel() {
  const { usuario, cerrarSesion } = useAuth();
  const [perfil, setPerfil] = useState<Usuario | null>(usuario);
  const [carnet, setCarnet] = useState<Documento[]>([]);
  const [vehiculos, setVehiculos] = useState<VehiculoConDocumentos[]>([]);
  const [error, setError] = useState<string | null>(null);

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

        {perfil && <TarjetaIdentidad perfil={perfil} carnet={carnet} onCambio={cargar} />}
        <TarjetaVehiculos vehiculos={vehiculos} onCambio={cargar} />

        <Link to="/mapa" className="block text-center text-sm text-emerald-700 underline">
          Ver mapa de cupos
        </Link>
      </div>
    </div>
  );
}

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

function TarjetaVehiculos({ vehiculos, onCambio }: { vehiculos: VehiculoConDocumentos[]; onCambio: () => void }) {
  return (
    <section className="space-y-3 rounded-2xl bg-white p-4 shadow-sm">
      <h2 className="font-semibold text-gray-900">Mis vehiculos</h2>
      {vehiculos.length === 0 && <p className="text-sm text-gray-400">Aun no has registrado ningun vehiculo.</p>}
      {vehiculos.map((vehiculo) => (
        <FilaVehiculo key={vehiculo.id} vehiculo={vehiculo} onCambio={onCambio} />
      ))}
      <FormularioVehiculo onCreado={onCambio} />
    </section>
  );
}

function FilaVehiculo({ vehiculo, onCambio }: { vehiculo: VehiculoConDocumentos; onCambio: () => void }) {
  const [fotoPlaca, setFotoPlaca] = useState<File | null>(null);
  const [tarjeta, setTarjeta] = useState<File | null>(null);
  const [enviando, setEnviando] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function reenviar(evento: FormEvent) {
    evento.preventDefault();
    if (!fotoPlaca || !tarjeta) return;
    setEnviando(true);
    setError(null);
    try {
      await reenviarDocumentosVehiculo(vehiculo.id, fotoPlaca, tarjeta);
      onCambio();
    } catch (err) {
      setError(mensajeDe(err, "No se pudieron reenviar los documentos"));
    } finally {
      setEnviando(false);
    }
  }

  return (
    <div className="space-y-2 rounded-xl border border-gray-200 p-3">
      <div className="flex items-center justify-between">
        <div>
          <p className="font-mono text-lg font-semibold text-gray-900">{vehiculo.placa}</p>
          <p className="text-sm capitalize text-gray-500">
            {[vehiculo.tipo_vehiculo, vehiculo.marca, vehiculo.color].filter(Boolean).join(" · ")}
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
              Foto de la placa
              <input
                type="file"
                required
                accept={ACEPTA_IMAGEN}
                onChange={(e) => setFotoPlaca(e.target.files?.[0] ?? null)}
                className="block w-full text-sm"
              />
            </label>
            <label className="block text-xs text-gray-600">
              Tarjeta de propiedad
              <input
                type="file"
                required
                accept={ACEPTA_IMAGEN_O_PDF}
                onChange={(e) => setTarjeta(e.target.files?.[0] ?? null)}
                className="block w-full text-sm"
              />
            </label>
            {error && <p className="text-sm text-red-600">{error}</p>}
            <Button type="submit" disabled={enviando || !fotoPlaca || !tarjeta}>
              {enviando ? "Enviando..." : "Reenviar"}
            </Button>
          </form>
        </>
      )}
    </div>
  );
}

function FormularioVehiculo({ onCreado }: { onCreado: () => void }) {
  const [abierto, setAbierto] = useState(false);
  const [placa, setPlaca] = useState("");
  const [tipo, setTipo] = useState<TipoVehiculo>("carro");
  const [marca, setMarca] = useState("");
  const [modelo, setModelo] = useState("");
  const [color, setColor] = useState("");
  const [fotoPlaca, setFotoPlaca] = useState<File | null>(null);
  const [tarjeta, setTarjeta] = useState<File | null>(null);
  const [enviando, setEnviando] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function enviar(evento: FormEvent) {
    evento.preventDefault();
    if (!fotoPlaca || !tarjeta) return;
    setEnviando(true);
    setError(null);
    try {
      await registrarMiVehiculo({
        placa,
        tipo_vehiculo: tipo,
        marca,
        modelo,
        color,
        foto_placa: fotoPlaca,
        tarjeta_propiedad: tarjeta,
      });
      setPlaca("");
      setMarca("");
      setModelo("");
      setColor("");
      setFotoPlaca(null);
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

  return (
    <form onSubmit={enviar} className="space-y-3 rounded-xl border border-emerald-200 p-3">
      <div className="grid gap-3 sm:grid-cols-2">
        <input
          required
          placeholder="Placa (ej. ABC123)"
          value={placa}
          maxLength={6}
          onChange={(e) => setPlaca(e.target.value.toUpperCase())}
          className={`${campo} font-mono uppercase`}
        />
        <select value={tipo} onChange={(e) => setTipo(e.target.value as TipoVehiculo)} className={campo}>
          <option value="carro">Carro</option>
          <option value="moto">Moto</option>
        </select>
        <input placeholder="Marca" value={marca} onChange={(e) => setMarca(e.target.value)} className={campo} />
        <input placeholder="Modelo" value={modelo} onChange={(e) => setModelo(e.target.value)} className={campo} />
        <input placeholder="Color" value={color} onChange={(e) => setColor(e.target.value)} className={campo} />
      </div>
      <label className="block text-sm text-gray-700">
        Foto de la placa del vehiculo
        <input
          type="file"
          required
          accept={ACEPTA_IMAGEN}
          onChange={(e) => setFotoPlaca(e.target.files?.[0] ?? null)}
          className="block w-full text-sm"
        />
      </label>
      <label className="block text-sm text-gray-700">
        Tarjeta de propiedad
        <input
          type="file"
          required
          accept={ACEPTA_IMAGEN_O_PDF}
          onChange={(e) => setTarjeta(e.target.files?.[0] ?? null)}
          className="block w-full text-sm"
        />
      </label>
      <p className="text-xs text-gray-500">JPG, PNG, WEBP (la tarjeta tambien PDF). Maximo 5 MB cada uno.</p>
      {error && <p className="text-sm text-red-600">{error}</p>}
      <div className="flex gap-2">
        <Button type="submit" disabled={enviando || !fotoPlaca || !tarjeta}>
          {enviando ? "Enviando..." : "Enviar para revision"}
        </Button>
        <Button type="button" variante="secundaria" onClick={() => setAbierto(false)}>
          Cancelar
        </Button>
      </div>
    </form>
  );
}
