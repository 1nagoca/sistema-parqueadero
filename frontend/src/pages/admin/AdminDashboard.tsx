import { useEffect, useState, type FormEvent } from "react";

import SpaceCell from "@/components/map/SpaceCell";
import Button from "@/components/common/Button";
import { useAuth } from "@/context/AuthContext";
import { listarAuditoria } from "@/services/api/auditoria";
import { ApiError } from "@/services/api/client";
import { crearEspacio, listarEspacios } from "@/services/api/espacios";
import { crearUsuario, listarUsuarios } from "@/services/api/usuarios";
import { crearZona, listarZonas } from "@/services/api/zonas";
import type { AuditoriaAcceso, Espacio, RolUsuario, Usuario, Zona } from "@/types/api";

type Pestana = "usuarios" | "zonas" | "espacios" | "auditoria";

const ETIQUETAS: Record<Pestana, string> = {
  usuarios: "Usuarios",
  zonas: "Zonas",
  espacios: "Espacios",
  auditoria: "Auditoria",
};

const campo = "min-h-12 rounded-lg border border-gray-300 px-3";

export default function AdminDashboard() {
  const { usuario, cerrarSesion } = useAuth();
  const [pestana, setPestana] = useState<Pestana>("usuarios");

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

      {pestana === "usuarios" && <SeccionUsuarios />}
      {pestana === "zonas" && <SeccionZonas />}
      {pestana === "espacios" && <SeccionEspacios />}
      {pestana === "auditoria" && <SeccionAuditoria />}
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
  const [rol, setRol] = useState<RolUsuario>("estudiante");
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
        <h2 className="font-semibold text-gray-900">Crear usuario</h2>
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
            <option value="estudiante">Estudiante</option>
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
              <th className="px-4 py-2">Activo</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {usuarios.map((u) => (
              <tr key={u.id}>
                <td className="px-4 py-2">{u.nombre_completo}</td>
                <td className="px-4 py-2">{u.correo_institucional}</td>
                <td className="px-4 py-2 capitalize">{u.rol}</td>
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

function SeccionAuditoria() {
  const [registros, setRegistros] = useState<AuditoriaAcceso[]>([]);
  const [filtro, setFiltro] = useState("");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    listarAuditoria(filtro || undefined)
      .then(setRegistros)
      .catch((err) => setError(err instanceof ApiError ? err.message : "No se pudo cargar la auditoria"));
  }, [filtro]);

  return (
    <div className="space-y-4">
      <div className="rounded-2xl bg-white p-4 shadow-sm">
        <label className="mb-1 block text-sm font-medium text-gray-700">Filtrar por tabla</label>
        <select value={filtro} onChange={(evento) => setFiltro(evento.target.value)} className={`${campo} w-full`}>
          <option value="">Todas</option>
          <option value="accesos">accesos</option>
          <option value="espacios">espacios</option>
          <option value="zonas">zonas</option>
        </select>
      </div>

      {error && <p className="rounded-xl bg-red-100 p-3 text-red-800">{error}</p>}

      <div className="space-y-2">
        {registros.map((registro) => (
          <div key={registro.id} className="rounded-xl bg-white p-3 text-sm shadow-sm">
            <p className="font-medium text-gray-900">
              {registro.tabla_afectada} · {registro.accion}
            </p>
            <p className="text-xs text-gray-500">{new Date(registro.fecha_hora).toLocaleString("es-CO")}</p>
            {registro.valores_nuevos && (
              <pre className="mt-1 overflow-x-auto text-xs text-gray-600">
                {JSON.stringify(registro.valores_nuevos)}
              </pre>
            )}
          </div>
        ))}
        {registros.length === 0 && <p className="text-center text-gray-400">Sin registros.</p>}
      </div>
    </div>
  );
}
