import { useEffect, useState, type FormEvent } from "react";

import SpaceCell from "@/components/map/SpaceCell";
import Button from "@/components/common/Button";
import DocumentoVisor from "@/components/verificacion/DocumentoVisor";
import EstadoBadge from "@/components/verificacion/EstadoBadge";
import { useAuth } from "@/context/AuthContext";
import { listarAuditoria, listarAuditoriaVerificaciones } from "@/services/api/auditoria";
import { ApiError } from "@/services/api/client";
import { crearEspacio, listarEspacios } from "@/services/api/espacios";
import { crearUsuario, listarUsuarios } from "@/services/api/usuarios";
import { listarPendientes, resolverUsuario, resolverVehiculo } from "@/services/api/verificaciones";
import { crearZona, listarZonas } from "@/services/api/zonas";
import type { AuditoriaAcceso, Espacio, RolUsuario, SolicitudVerificacion, Usuario, Zona } from "@/types/api";

type Pestana = "verificaciones" | "usuarios" | "zonas" | "espacios" | "auditoria";

const ETIQUETAS: Record<Pestana, string> = {
  verificaciones: "Verificaciones",
  usuarios: "Usuarios",
  zonas: "Zonas",
  espacios: "Espacios",
  auditoria: "Auditoria",
};

const campo = "min-h-12 rounded-lg border border-gray-300 px-3";

export default function AdminDashboard() {
  const { usuario, cerrarSesion } = useAuth();
  const [pestana, setPestana] = useState<Pestana>("verificaciones");

  return (
    <div className="min-h-screen bg-gray-100 p-4 pb-24 sm:p-6">
      <header className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-gray-900 sm:text-2xl">Panel de Administracion</h1>
          {usuario && <p className="text-sm text-gray-500">{usuario.nombre_completo}</p>}
        </div>
        <button onClick={cerrarSesion} className="text-sm text-gray-500 underline">
          Cerrar sesion
        </button>
      </header>

      <nav className="mb-4 flex gap-2 overflow-x-auto">
        {(Object.keys(ETIQUETAS) as Pestana[]).map((valor) => (
          <button
            key={valor}
            onClick={() => setPestana(valor)}
            className={`whitespace-nowrap rounded-full px-4 py-2 text-sm font-medium ${
              pestana === valor ? "bg-emerald-600 text-white" : "bg-white text-gray-600"
            }`}
          >
            {ETIQUETAS[valor]}
          </button>
        ))}
      </nav>

      {pestana === "verificaciones" && <SeccionVerificaciones />}
      {pestana === "usuarios" && <SeccionUsuarios />}
      {pestana === "zonas" && <SeccionZonas />}
      {pestana === "espacios" && <SeccionEspacios />}
      {pestana === "auditoria" && <SeccionAuditoria />}
    </div>
  );
}

function SeccionVerificaciones() {
  const [solicitudes, setSolicitudes] = useState<SolicitudVerificacion[]>([]);
  const [cargando, setCargando] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [mensaje, setMensaje] = useState<string | null>(null);
  const [procesando, setProcesando] = useState(false);

  useEffect(() => {
    cargar();
  }, []);

  async function cargar() {
    try {
      setSolicitudes(await listarPendientes());
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "No se pudo cargar la bandeja");
    } finally {
      setCargando(false);
    }
  }

  /** Aprobar no pide nada; rechazar pide el motivo para que el estudiante sepa que corregir. */
  async function resolver(tipo: "usuario" | "vehiculo", id: string, aprobar: boolean) {
    let motivo: string | undefined;
    if (!aprobar) {
      const respuesta = window.prompt("Motivo del rechazo (el estudiante lo vera):");
      if (!respuesta?.trim()) return;
      motivo = respuesta.trim();
    }
    setProcesando(true);
    setError(null);
    setMensaje(null);
    try {
      if (tipo === "usuario") await resolverUsuario(id, aprobar, motivo);
      else await resolverVehiculo(id, aprobar, motivo);
      setMensaje(aprobar ? "Aprobado" : "Rechazado");
      await cargar();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "No se pudo registrar la decision");
    } finally {
      setProcesando(false);
    }
  }

  return (
    <div className="space-y-4">
      {mensaje && <p className="rounded-xl bg-emerald-100 p-3 text-emerald-800">{mensaje}</p>}
      {error && <p className="rounded-xl bg-red-100 p-3 text-red-800">{error}</p>}
      {cargando && <p className="text-center text-gray-400">Cargando...</p>}
      {!cargando && solicitudes.length === 0 && (
        <p className="rounded-2xl bg-white p-6 text-center text-gray-400 shadow-sm">No hay solicitudes pendientes.</p>
      )}

      {solicitudes.map(({ usuario, vehiculos }) => (
        <section key={usuario.id} className="space-y-4 rounded-2xl bg-white p-4 shadow-sm">
          <div className="flex flex-wrap items-start justify-between gap-2">
            <div>
              <h2 className="font-semibold text-gray-900">{usuario.nombre_completo}</h2>
              <p className="text-sm text-gray-500">
                {usuario.correo_institucional} · Doc. {usuario.documento_identidad}
              </p>
              {usuario.universidad && <p className="text-sm text-gray-500">{usuario.universidad}</p>}
            </div>
            <EstadoBadge estado={usuario.estado_verificacion} />
          </div>

          {usuario.estado_verificacion === "pendiente" && usuario.documentos.length > 0 && (
            <div className="space-y-2 rounded-xl border border-gray-200 p-3">
              <p className="text-sm font-medium text-gray-700">
                Identidad: verifica que el carnet o Divisist muestre su nombre y que estudia en la universidad
              </p>
              <div className="flex flex-wrap gap-4">
                {usuario.documentos.map((doc) => (
                  <DocumentoVisor key={doc.id} documento={doc} />
                ))}
              </div>
              <div className="flex gap-2">
                <Button disabled={procesando} onClick={() => resolver("usuario", usuario.id, true)}>
                  Aprobar estudiante
                </Button>
                <Button variante="peligro" disabled={procesando} onClick={() => resolver("usuario", usuario.id, false)}>
                  Rechazar
                </Button>
              </div>
            </div>
          )}

          {vehiculos.map((vehiculo) => (
            <div key={vehiculo.id} className="space-y-2 rounded-xl border border-gray-200 p-3">
              <p className="text-sm font-medium text-gray-700">
                Vehiculo <span className="font-mono text-base font-semibold">{vehiculo.placa}</span>{" "}
                <span className="capitalize text-gray-500">
                  ({[vehiculo.tipo_vehiculo, vehiculo.marca, vehiculo.color].filter(Boolean).join(", ")})
                </span>
              </p>
              <p className="text-xs text-gray-500">La placa de la foto y de la tarjeta de propiedad deben coincidir.</p>
              <div className="flex flex-wrap gap-4">
                {vehiculo.documentos.map((doc) => (
                  <DocumentoVisor key={doc.id} documento={doc} />
                ))}
              </div>
              <div className="flex gap-2">
                <Button disabled={procesando} onClick={() => resolver("vehiculo", vehiculo.id, true)}>
                  Aprobar vehiculo
                </Button>
                <Button variante="peligro" disabled={procesando} onClick={() => resolver("vehiculo", vehiculo.id, false)}>
                  Rechazar
                </Button>
              </div>
            </div>
          ))}
        </section>
      ))}
    </div>
  );
}

function SeccionUsuarios() {
  const [usuarios, setUsuarios] = useState<Usuario[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [mensaje, setMensaje] = useState<string | null>(null);
  const [procesando, setProcesando] = useState(false);

  const [nombreCompleto, setNombreCompleto] = useState("");
  const [correo, setCorreo] = useState("");
  const [documento, setDocumento] = useState("");
  const [rol, setRol] = useState<RolUsuario>("vigilante");
  const [password, setPassword] = useState("");

  useEffect(() => {
    cargar();
  }, []);

  async function cargar() {
    try {
      setUsuarios(await listarUsuarios());
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "No se pudieron cargar los usuarios");
    }
  }

  async function crear(evento: FormEvent) {
    evento.preventDefault();
    setProcesando(true);
    setError(null);
    setMensaje(null);
    try {
      await crearUsuario({
        nombre_completo: nombreCompleto,
        correo_institucional: correo,
        documento_identidad: documento,
        rol,
        password,
      });
      setMensaje("Usuario creado");
      setNombreCompleto("");
      setCorreo("");
      setDocumento("");
      setPassword("");
      cargar();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "No se pudo crear el usuario");
    } finally {
      setProcesando(false);
    }
  }

  return (
    <div className="space-y-4">
      <form onSubmit={crear} className="space-y-3 rounded-2xl bg-white p-4 shadow-sm">
        <h2 className="font-semibold text-gray-900">Crear usuario del personal</h2>
        <p className="text-xs text-gray-500">
          Los estudiantes se registran ellos mismos desde la pagina de registro: asi el administrador nunca conoce su
          contraseña.
        </p>
        <div className="grid gap-3 sm:grid-cols-2">
          <input
            required
            placeholder="Nombre completo"
            value={nombreCompleto}
            onChange={(evento) => setNombreCompleto(evento.target.value)}
            className={campo}
          />
          <input
            required
            type="email"
            placeholder="Correo institucional"
            value={correo}
            onChange={(evento) => setCorreo(evento.target.value)}
            className={campo}
          />
          <input
            required
            placeholder="Documento de identidad"
            value={documento}
            onChange={(evento) => setDocumento(evento.target.value)}
            className={campo}
          />
          <select value={rol} onChange={(evento) => setRol(evento.target.value as RolUsuario)} className={campo}>
            <option value="docente">Docente</option>
            <option value="administrativo">Administrativo</option>
            <option value="vigilante">Vigilante</option>
            <option value="admin">Admin</option>
          </select>
          <input
            required
            type="password"
            placeholder="Contraseña"
            value={password}
            onChange={(evento) => setPassword(evento.target.value)}
            className={campo}
          />
        </div>
        <Button type="submit" disabled={procesando}>
          Crear usuario
        </Button>
      </form>

      {mensaje && <p className="rounded-xl bg-emerald-100 p-3 text-emerald-800">{mensaje}</p>}
      {error && <p className="rounded-xl bg-red-100 p-3 text-red-800">{error}</p>}

      <div className="overflow-hidden rounded-2xl bg-white shadow-sm">
        <table className="w-full text-left text-sm">
          <thead className="bg-gray-50 text-gray-500">
            <tr>
              <th className="px-4 py-2">Nombre</th>
              <th className="px-4 py-2">Correo</th>
              <th className="px-4 py-2">Rol</th>
              <th className="px-4 py-2">Verificacion</th>
              <th className="px-4 py-2">Activo</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {usuarios.map((u) => (
              <tr key={u.id}>
                <td className="px-4 py-2">{u.nombre_completo}</td>
                <td className="px-4 py-2">{u.correo_institucional}</td>
                <td className="px-4 py-2 capitalize">{u.rol}</td>
                <td className="px-4 py-2">
                  <EstadoBadge estado={u.estado_verificacion} />
                </td>
                <td className="px-4 py-2">{u.activo ? "Si" : "No"}</td>
              </tr>
            ))}
          </tbody>
        </table>
        {usuarios.length === 0 && <p className="p-4 text-center text-gray-400">Sin usuarios todavia.</p>}
      </div>
    </div>
  );
}

function SeccionZonas() {
  const [zonas, setZonas] = useState<Zona[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [mensaje, setMensaje] = useState<string | null>(null);
  const [procesando, setProcesando] = useState(false);

  const [nombre, setNombre] = useState("");
  const [ubicacion, setUbicacion] = useState("");
  const [capacidad, setCapacidad] = useState(10);

  useEffect(() => {
    cargar();
  }, []);

  async function cargar() {
    try {
      setZonas(await listarZonas());
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "No se pudieron cargar las zonas");
    }
  }

  async function crear(evento: FormEvent) {
    evento.preventDefault();
    setProcesando(true);
    setError(null);
    setMensaje(null);
    try {
      await crearZona({ nombre, ubicacion_descripcion: ubicacion || null, capacidad_total: capacidad });
      setMensaje("Zona creada");
      setNombre("");
      setUbicacion("");
      setCapacidad(10);
      cargar();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "No se pudo crear la zona");
    } finally {
      setProcesando(false);
    }
  }

  return (
    <div className="space-y-4">
      <form onSubmit={crear} className="space-y-3 rounded-2xl bg-white p-4 shadow-sm">
        <h2 className="font-semibold text-gray-900">Crear zona</h2>
        <div className="grid gap-3 sm:grid-cols-3">
          <input
            required
            placeholder="Nombre"
            value={nombre}
            onChange={(evento) => setNombre(evento.target.value)}
            className={campo}
          />
          <input
            placeholder="Ubicacion (opcional)"
            value={ubicacion}
            onChange={(evento) => setUbicacion(evento.target.value)}
            className={campo}
          />
          <input
            required
            type="number"
            min={1}
            placeholder="Capacidad total"
            value={capacidad}
            onChange={(evento) => setCapacidad(Number(evento.target.value))}
            className={campo}
          />
        </div>
        <Button type="submit" disabled={procesando}>
          Crear zona
        </Button>
      </form>

      {mensaje && <p className="rounded-xl bg-emerald-100 p-3 text-emerald-800">{mensaje}</p>}
      {error && <p className="rounded-xl bg-red-100 p-3 text-red-800">{error}</p>}

      <div className="overflow-hidden rounded-2xl bg-white shadow-sm">
        <table className="w-full text-left text-sm">
          <thead className="bg-gray-50 text-gray-500">
            <tr>
              <th className="px-4 py-2">Nombre</th>
              <th className="px-4 py-2">Ubicacion</th>
              <th className="px-4 py-2">Cupos</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {zonas.map((z) => (
              <tr key={z.id}>
                <td className="px-4 py-2">{z.nombre}</td>
                <td className="px-4 py-2">{z.ubicacion_descripcion ?? "—"}</td>
                <td className="px-4 py-2">
                  {z.cupos_disponibles}/{z.capacidad_total}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function SeccionEspacios() {
  const [zonas, setZonas] = useState<Zona[]>([]);
  const [zonaId, setZonaId] = useState("");
  const [espacios, setEspacios] = useState<Espacio[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [mensaje, setMensaje] = useState<string | null>(null);
  const [procesando, setProcesando] = useState(false);
  const [codigo, setCodigo] = useState("");
  const [tipoEspacio, setTipoEspacio] = useState("");

  useEffect(() => {
    listarZonas()
      .then((datos) => {
        setZonas(datos);
        setZonaId((actual) => actual || datos[0]?.id || "");
      })
      .catch(() => setError("No se pudieron cargar las zonas"));
  }, []);

  useEffect(() => {
    if (!zonaId) return;
    listarEspacios(zonaId).then(setEspacios).catch(() => setEspacios([]));
  }, [zonaId]);

  async function crear(evento: FormEvent) {
    evento.preventDefault();
    if (!zonaId) return;
    setProcesando(true);
    setError(null);
    setMensaje(null);
    try {
      await crearEspacio({ zona_id: zonaId, codigo, tipo_espacio: tipoEspacio || null });
      setMensaje("Espacio creado");
      setCodigo("");
      setTipoEspacio("");
      listarEspacios(zonaId).then(setEspacios);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "No se pudo crear el espacio");
    } finally {
      setProcesando(false);
    }
  }

  return (
    <div className="space-y-4">
      <div className="rounded-2xl bg-white p-4 shadow-sm">
        <label className="mb-1 block text-sm font-medium text-gray-700">Zona</label>
        <select value={zonaId} onChange={(evento) => setZonaId(evento.target.value)} className={`${campo} w-full`}>
          {zonas.map((z) => (
            <option key={z.id} value={z.id}>
              {z.nombre}
            </option>
          ))}
        </select>
      </div>

      <form onSubmit={crear} className="space-y-3 rounded-2xl bg-white p-4 shadow-sm">
        <h2 className="font-semibold text-gray-900">Crear espacio en esta zona</h2>
        <div className="grid gap-3 sm:grid-cols-2">
          <input
            required
            placeholder="Codigo (ej. A-09)"
            value={codigo}
            onChange={(evento) => setCodigo(evento.target.value.toUpperCase())}
            className={campo}
          />
          <input
            placeholder="Tipo (opcional, ej. discapacidad)"
            value={tipoEspacio}
            onChange={(evento) => setTipoEspacio(evento.target.value)}
            className={campo}
          />
        </div>
        <Button type="submit" disabled={procesando || !zonaId}>
          Crear espacio
        </Button>
      </form>

      {mensaje && <p className="rounded-xl bg-emerald-100 p-3 text-emerald-800">{mensaje}</p>}
      {error && <p className="rounded-xl bg-red-100 p-3 text-red-800">{error}</p>}

      <div className="grid grid-cols-4 gap-2 sm:grid-cols-6">
        {espacios.map((espacio) => (
          <SpaceCell key={espacio.id} codigo={espacio.codigo} estado={espacio.estado} />
        ))}
        {espacios.length === 0 && (
          <p className="col-span-full text-center text-gray-400">Esta zona no tiene espacios individuales.</p>
        )}
      </div>
    </div>
  );
}

type OrigenAuditoria = "accesos" | "verificaciones";

/** Cada origen es un microservicio distinto: accesos guarda entradas y salidas; identidad, las
 * verificaciones. Se cargan por separado para que la caida de uno no oculte al otro. */
const ORIGENES: Record<
  OrigenAuditoria,
  { etiqueta: string; estilo: string; listar: (tabla?: string) => Promise<AuditoriaAcceso[]>; error: string }
> = {
  accesos: {
    etiqueta: "Accesos",
    estilo: "bg-sky-100 text-sky-800",
    listar: listarAuditoria,
    error: "No se pudo cargar la auditoria de accesos. Se muestran solo las verificaciones.",
  },
  verificaciones: {
    etiqueta: "Verificaciones",
    estilo: "bg-amber-100 text-amber-800",
    listar: listarAuditoriaVerificaciones,
    error: "No se pudo cargar la auditoria de verificaciones. Se muestran solo los accesos.",
  },
};

const ORIGENES_AUDITORIA = Object.keys(ORIGENES) as OrigenAuditoria[];

type CargaAuditoria = { registros: AuditoriaAcceso[]; error: boolean; cargando: boolean };

const CARGA_INICIAL: Record<OrigenAuditoria, CargaAuditoria> = {
  accesos: { registros: [], error: false, cargando: true },
  verificaciones: { registros: [], error: false, cargando: true },
};

function SeccionAuditoria() {
  const [cargas, setCargas] = useState(CARGA_INICIAL);
  const [filtro, setFiltro] = useState("");

  useEffect(() => {
    // Si el filtro cambia antes de que llegue una respuesta, esa respuesta ya no se usa.
    let vigente = true;
    setCargas(CARGA_INICIAL);
    for (const origen of ORIGENES_AUDITORIA) {
      ORIGENES[origen]
        .listar(filtro || undefined)
        .then((registros) => ({ registros, error: false, cargando: false }))
        .catch(() => ({ registros: [], error: true, cargando: false }))
        .then((carga) => {
          if (vigente) setCargas((actual) => ({ ...actual, [origen]: carga }));
        });
    }
    return () => {
      vigente = false;
    };
  }, [filtro]);

  const registros = ORIGENES_AUDITORIA.flatMap((origen) =>
    cargas[origen].registros.map((registro) => ({ origen, registro })),
  ).sort((a, b) => new Date(b.registro.fecha_hora).getTime() - new Date(a.registro.fecha_hora).getTime());
  const cargando = ORIGENES_AUDITORIA.some((origen) => cargas[origen].cargando);

  return (
    <div className="space-y-4">
      <div className="rounded-2xl bg-white p-4 shadow-sm">
        <label className="mb-1 block text-sm font-medium text-gray-700">Filtrar por tabla</label>
        <select value={filtro} onChange={(evento) => setFiltro(evento.target.value)} className={`${campo} w-full`}>
          <option value="">Todas</option>
          <option value="accesos">accesos</option>
          <option value="usuarios">usuarios</option>
          <option value="vehiculos">vehiculos</option>
          <option value="espacios">espacios</option>
          <option value="zonas">zonas</option>
        </select>
      </div>

      {ORIGENES_AUDITORIA.filter((origen) => cargas[origen].error).map((origen) => (
        <p key={origen} className="rounded-xl bg-red-100 p-3 text-red-800">
          {ORIGENES[origen].error}
        </p>
      ))}

      <div className="space-y-2">
        {registros.map(({ origen, registro }) => (
          <div key={`${origen}-${registro.id}`} className="rounded-xl bg-white p-3 text-sm shadow-sm">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <p className="font-medium text-gray-900">
                {registro.tabla_afectada} · {registro.accion}
              </p>
              <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${ORIGENES[origen].estilo}`}>
                {ORIGENES[origen].etiqueta}
              </span>
            </div>
            <p className="text-xs text-gray-500">{new Date(registro.fecha_hora).toLocaleString("es-CO")}</p>
            {registro.motivo && <p className="mt-1 text-xs text-gray-700">Motivo: {registro.motivo}</p>}
            {registro.valores_nuevos && (
              <pre className="mt-1 overflow-x-auto text-xs text-gray-600">
                {JSON.stringify(registro.valores_nuevos)}
              </pre>
            )}
          </div>
        ))}
        {cargando && registros.length === 0 && <p className="text-center text-gray-400">Cargando...</p>}
        {!cargando && registros.length === 0 && <p className="text-center text-gray-400">Sin registros.</p>}
      </div>
    </div>
  );
}
