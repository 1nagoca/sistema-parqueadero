import { Fragment, useCallback, useEffect, useState, type FormEvent } from "react";

import MapaParqueadero from "@/components/map/MapaParqueadero";
import { CODIGOS_PLANO } from "@/components/map/planoParqueadero";
import Button from "@/components/common/Button";
import DocumentoVisor from "@/components/verificacion/DocumentoVisor";
import EstadoBadge from "@/components/verificacion/EstadoBadge";
import { useAuth } from "@/context/AuthContext";
import { listarAuditoria, listarAuditoriaVerificaciones } from "@/services/api/auditoria";
import { ApiError } from "@/services/api/client";
import { crearEspaciosLote, listarEspacios } from "@/services/api/espacios";
import { crearUsuario, darDeBajaUsuario, listarUsuarios, reactivarUsuario } from "@/services/api/usuarios";
import { listarPendientes, resolverUsuario, resolverVehiculo } from "@/services/api/verificaciones";
import { crearZona, listarZonas } from "@/services/api/zonas";
import { useActualizacionesZona } from "@/services/realtime/useActualizacionesZona";
import type {
  AuditoriaPagina,
  Espacio,
  FiltrosAuditoria,
  RolUsuario,
  SolicitudVerificacion,
  Usuario,
  UsuariosPagina,
  Zona,
} from "@/types/api";

// Pestanas del panel y su titulo.
type Pestana = "verificaciones" | "usuarios" | "zonas" | "espacios" | "auditoria";

const ETIQUETAS: Record<Pestana, string> = {
  verificaciones: "Verificaciones",
  usuarios: "Usuarios",
  zonas: "Zonas",
  espacios: "Espacios",
  auditoria: "Auditoria",
};

// Estilo comun de los campos.
const campo = "min-h-12 rounded-lg border border-gray-300 px-3";

// Colombia es UTC-5 fijo (no tiene horario de verano).
const DESFASE_COLOMBIA_MS = 5 * 60 * 60 * 1000;

// Fecha de hoy en Colombia como AAAA-MM-DD.
function hoyEnColombia(): string {
  return new Date(Date.now() - DESFASE_COLOMBIA_MS).toISOString().slice(0, 10);
}

// Suma dias a una fecha AAAA-MM-DD (con negativos resta).
function sumarDias(fecha: string, dias: number): string {
  const dia = new Date(`${fecha}T00:00:00Z`);
  dia.setUTCDate(dia.getUTCDate() + dias);
  return dia.toISOString().slice(0, 10);
}

// Semestre de una fecha: enero a junio es AAAA-1 y julio a diciembre AAAA-2.
function semestreDe(fecha: string): { nombre: string; desde: string; hasta: string } {
  const anio = fecha.slice(0, 4);
  return Number(fecha.slice(5, 7)) <= 6
    ? { nombre: `${anio}-1`, desde: `${anio}-01-01`, hasta: `${anio}-06-30` }
    : { nombre: `${anio}-2`, desde: `${anio}-07-01`, hasta: `${anio}-12-31` };
}

// Panel del administrador: una pestana por tarea.
export default function AdminDashboard() {
  const { usuario, cerrarSesion } = useAuth();
  const [pestana, setPestana] = useState<Pestana>("verificaciones");

  return (
    <div className="min-h-screen bg-gray-100 p-4 pb-24 sm:p-6">
      <header className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-gray-900 sm:text-2xl">Panel de Administracion</h1>
          <p className="flex flex-wrap items-center gap-2 text-sm text-gray-500">
            {usuario && <span>{usuario.nombre_completo}</span>}
            <span className="rounded-full bg-emerald-100 px-2 py-0.5 text-xs font-medium text-emerald-800">
              Semestre {semestreDe(hoyEnColombia()).nombre}
            </span>
          </p>
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

// Bandeja para aprobar o rechazar estudiantes y vehiculos.
function SeccionVerificaciones() {
  const [solicitudes, setSolicitudes] = useState<SolicitudVerificacion[]>([]);
  const [cargando, setCargando] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [mensaje, setMensaje] = useState<string | null>(null);
  const [procesando, setProcesando] = useState(false);

  useEffect(() => {
    cargar();
  }, []);

  // Trae las solicitudes pendientes.
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

// Motivos sugeridos de baja segun el rol; siempre se puede escribir otro.
const MOTIVOS_BAJA: Partial<Record<RolUsuario, string[]>> = {
  estudiante: ["Se graduó", "Se retiró de la universidad"],
  vigilante: ["Despedido", "Renunció"],
};
const OTRO_MOTIVO = "Otro";
const USUARIOS_POR_PAGINA = 20;

// Lista paginada de usuarios con buscador, filtros, baja y reactivacion, y formulario para crear personal.
function SeccionUsuarios() {
  const { usuario: yo } = useAuth();
  const [pagina, setPagina] = useState<UsuariosPagina | null>(null);
  const [numeroPagina, setNumeroPagina] = useState(1);
  const [buscar, setBuscar] = useState("");
  const [buscarAplicado, setBuscarAplicado] = useState("");
  const [filtroRol, setFiltroRol] = useState<"" | RolUsuario>("");
  const [filtroActivo, setFiltroActivo] = useState<"" | "true" | "false">("");
  const [recarga, setRecarga] = useState(0);
  const [cargando, setCargando] = useState(true);
  const [errorLista, setErrorLista] = useState<string | null>(null);
  const [bajaAbierta, setBajaAbierta] = useState<string | null>(null);
  const [reactivando, setReactivando] = useState<string | null>(null);

  const [error, setError] = useState<string | null>(null);
  const [mensaje, setMensaje] = useState<string | null>(null);
  const [procesando, setProcesando] = useState(false);

  const [nombreCompleto, setNombreCompleto] = useState("");
  const [correo, setCorreo] = useState("");
  const [documento, setDocumento] = useState("");
  const [rol, setRol] = useState<RolUsuario>("vigilante");
  const [password, setPassword] = useState("");

  // Espera 300 ms despues de la ultima tecla y vuelve a la primera pagina.
  useEffect(() => {
    const espera = setTimeout(() => {
      setBuscarAplicado(buscar);
      setNumeroPagina(1);
    }, 300);
    return () => clearTimeout(espera);
  }, [buscar]);

  useEffect(() => {
    // Si los filtros cambian antes de que llegue la respuesta, esa respuesta ya no se usa.
    let vigente = true;
    setCargando(true);
    listarUsuarios({
      pagina: numeroPagina,
      por_pagina: USUARIOS_POR_PAGINA,
      buscar: buscarAplicado,
      rol: filtroRol || undefined,
      activo: filtroActivo === "" ? undefined : filtroActivo === "true",
    })
      .then((resultado) => {
        if (!vigente) return;
        // Si la pagina quedo vacia (por ejemplo tras una baja) vuelve a la anterior.
        if (resultado.items.length === 0 && numeroPagina > 1) {
          setNumeroPagina(numeroPagina - 1);
          return;
        }
        setPagina(resultado);
        setErrorLista(null);
      })
      .catch((err) => {
        if (vigente) setErrorLista(err instanceof ApiError ? err.message : "No se pudieron cargar los usuarios");
      })
      .finally(() => {
        if (vigente) setCargando(false);
      });
    return () => {
      vigente = false;
    };
  }, [numeroPagina, buscarAplicado, filtroRol, filtroActivo, recarga]);

  // Vuelve a pedir la pagina actual.
  function recargar() {
    setRecarga((n) => n + 1);
  }

  // Crea el usuario y recarga la lista.
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
      recargar();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "No se pudo crear el usuario");
    } finally {
      setProcesando(false);
    }
  }

  // Reactiva al usuario; el estudiante debe volver a subir sus documentos.
  async function reactivar(u: Usuario) {
    setReactivando(u.id);
    setError(null);
    setMensaje(null);
    try {
      await reactivarUsuario(u.id);
      setMensaje(
        u.rol === "estudiante"
          ? `${u.nombre_completo} fue reactivado: debe subir de nuevo su carnet y los documentos de sus motos.`
          : `${u.nombre_completo} fue reactivado.`,
      );
      recargar();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "No se pudo reactivar al usuario");
    } finally {
      setReactivando(null);
    }
  }

  // Cierra el panel de baja, avisa y recarga la lista.
  function bajaHecha(u: Usuario) {
    setBajaAbierta(null);
    setError(null);
    setMensaje(`${u.nombre_completo} quedó dado de baja y se borraron sus documentos.`);
    recargar();
  }

  const items = pagina?.items ?? [];
  const total = pagina?.total ?? 0;
  const desde = pagina && total > 0 ? (pagina.pagina - 1) * pagina.por_pagina + 1 : 0;
  const hasta = pagina ? (pagina.pagina - 1) * pagina.por_pagina + items.length : 0;

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
            <option value="vigilante">Vigilante</option>
            <option value="admin">Administrador</option>
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

      <div className="rounded-2xl bg-white shadow-sm">
        <div className="grid gap-3 p-4 sm:grid-cols-[1fr_auto_auto]">
          <input
            type="search"
            placeholder="Buscar por nombre, correo o documento"
            value={buscar}
            onChange={(evento) => setBuscar(evento.target.value)}
            className={campo}
          />
          <select
            value={filtroRol}
            onChange={(evento) => {
              setFiltroRol(evento.target.value as "" | RolUsuario);
              setNumeroPagina(1);
            }}
            className={campo}
          >
            <option value="">Todos los roles</option>
            <option value="estudiante">Estudiante</option>
            <option value="vigilante">Vigilante</option>
            <option value="admin">Administrador</option>
          </select>
          <select
            value={filtroActivo}
            onChange={(evento) => {
              setFiltroActivo(evento.target.value as "" | "true" | "false");
              setNumeroPagina(1);
            }}
            className={campo}
          >
            <option value="">Activos y dados de baja</option>
            <option value="true">Activos</option>
            <option value="false">Dados de baja</option>
          </select>
        </div>

        {errorLista && <p className="mx-4 mb-4 rounded-xl bg-red-100 p-3 text-red-800">{errorLista}</p>}

        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead className="bg-gray-50 text-gray-500">
              <tr>
                <th className="px-4 py-2">Nombre</th>
                <th className="px-4 py-2">Correo</th>
                <th className="px-4 py-2">Rol</th>
                <th className="px-4 py-2">Verificacion</th>
                <th className="px-4 py-2">Activo</th>
                <th className="px-4 py-2">Acción</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {items.map((u) => (
                <Fragment key={u.id}>
                  <tr>
                    <td className="px-4 py-2">{u.nombre_completo}</td>
                    <td className="px-4 py-2">{u.correo_institucional}</td>
                    <td className="px-4 py-2 capitalize">{u.rol === "admin" ? "Administrador" : u.rol}</td>
                    <td className="px-4 py-2">
                      <EstadoBadge estado={u.estado_verificacion} />
                    </td>
                    <td className="px-4 py-2">
                      <span
                        className={`rounded-full px-2 py-0.5 text-xs font-medium ${
                          u.activo ? "bg-emerald-100 text-emerald-800" : "bg-gray-200 text-gray-700"
                        }`}
                      >
                        {u.activo ? "Activo" : "De baja"}
                      </span>
                    </td>
                    <td className="whitespace-nowrap px-4 py-2">
                      {u.id === yo?.id ? (
                        <span className="text-xs text-gray-400">Tu cuenta</span>
                      ) : !MOTIVOS_BAJA[u.rol] ? (
                        <span className="text-gray-300">—</span>
                      ) : u.activo ? (
                        <button
                          onClick={() => setBajaAbierta(bajaAbierta === u.id ? null : u.id)}
                          className="rounded-lg border border-red-300 px-3 py-1 text-sm font-medium text-red-700 hover:bg-red-50"
                        >
                          Dar de baja
                        </button>
                      ) : (
                        <button
                          onClick={() => reactivar(u)}
                          disabled={reactivando === u.id}
                          className="rounded-lg border border-emerald-300 px-3 py-1 text-sm font-medium text-emerald-700 hover:bg-emerald-50 disabled:opacity-50"
                        >
                          Reactivar
                        </button>
                      )}
                    </td>
                  </tr>
                  {bajaAbierta === u.id && (
                    <tr>
                      <td colSpan={6} className="bg-red-50 px-4 py-3">
                        <PanelBaja usuario={u} onHecho={() => bajaHecha(u)} onCancelar={() => setBajaAbierta(null)} />
                      </td>
                    </tr>
                  )}
                </Fragment>
              ))}
            </tbody>
          </table>
        </div>
        {!cargando && items.length === 0 && !errorLista && (
          <p className="p-4 text-center text-gray-400">Sin usuarios con esos filtros.</p>
        )}

        <div className="flex flex-wrap items-center justify-between gap-2 border-t border-gray-100 p-4 text-sm">
          <span className="text-gray-500">{cargando ? "Cargando..." : `Mostrando ${desde}–${hasta} de ${total}`}</span>
          <div className="flex gap-2">
            <button
              onClick={() => setNumeroPagina(numeroPagina - 1)}
              disabled={cargando || numeroPagina <= 1}
              className="rounded-lg bg-gray-100 px-3 py-1 text-gray-700 disabled:opacity-40"
            >
              ← Anterior
            </button>
            <button
              onClick={() => setNumeroPagina(numeroPagina + 1)}
              disabled={cargando || hasta >= total}
              className="rounded-lg bg-gray-100 px-3 py-1 text-gray-700 disabled:opacity-40"
            >
              Siguiente →
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

// Formulario de baja en la fila: motivo sugerido segun el rol u otro escrito a mano.
function PanelBaja({
  usuario,
  onHecho,
  onCancelar,
}: {
  usuario: Usuario;
  onHecho: () => void;
  onCancelar: () => void;
}) {
  const sugeridos = MOTIVOS_BAJA[usuario.rol] ?? [];
  const [opcion, setOpcion] = useState(sugeridos[0] ?? OTRO_MOTIVO);
  const [otro, setOtro] = useState("");
  const [procesando, setProcesando] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const motivo = opcion === OTRO_MOTIVO ? otro.trim() : opcion;
  const motivoValido = motivo.length >= 3 && motivo.length <= 200;

  // Envia la baja; si falla, muestra el error en el mismo panel.
  async function confirmar() {
    setProcesando(true);
    setError(null);
    try {
      await darDeBajaUsuario(usuario.id, motivo);
      onHecho();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "No se pudo dar de baja al usuario");
      setProcesando(false);
    }
  }

  return (
    <div className="space-y-2">
      <p className="font-medium text-gray-900">Dar de baja a {usuario.nombre_completo}</p>
      <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
        {[...sugeridos, OTRO_MOTIVO].map((valor) => (
          <label key={valor} className="flex items-center gap-1">
            <input
              type="radio"
              name={`motivo-${usuario.id}`}
              checked={opcion === valor}
              onChange={() => setOpcion(valor)}
            />
            {valor}
          </label>
        ))}
        {opcion === OTRO_MOTIVO && (
          <input
            autoFocus
            maxLength={200}
            placeholder="Escribe el motivo"
            value={otro}
            onChange={(evento) => setOtro(evento.target.value)}
            className="min-h-10 flex-1 rounded-lg border border-gray-300 px-3"
          />
        )}
      </div>
      <p className="text-xs text-gray-600">
        {usuario.rol === "estudiante"
          ? "Se borrarán su carnet y los documentos de sus motos. Sus motos y su historial de accesos se conservan."
          : "No podrá iniciar sesión. Su historial se conserva."}
      </p>
      {error && <p className="rounded-lg bg-red-100 p-2 text-red-800">{error}</p>}
      <div className="flex gap-2">
        <button
          onClick={confirmar}
          disabled={procesando || !motivoValido}
          className="rounded-lg bg-red-600 px-4 py-2 font-medium text-white hover:bg-red-700 disabled:opacity-50"
        >
          Confirmar baja
        </button>
        <button onClick={onCancelar} disabled={procesando} className="rounded-lg bg-gray-200 px-4 py-2 text-gray-800">
          Cancelar
        </button>
      </div>
    </div>
  );
}

// Lista de zonas y formulario para crear una.
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

  // Trae las zonas.
  async function cargar() {
    try {
      setZonas(await listarZonas());
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "No se pudieron cargar las zonas");
    }
  }

  // Crea la zona y recarga la lista.
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

// Mapa de los puestos de una zona y boton para crear los del plano.
function SeccionEspacios() {
  const [zonas, setZonas] = useState<Zona[]>([]);
  const [zonaId, setZonaId] = useState("");
  const [espacios, setEspacios] = useState<Espacio[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [mensaje, setMensaje] = useState<string | null>(null);
  const [procesando, setProcesando] = useState(false);

  // Carga las zonas y elige la primera.
  const cargarZonas = useCallback(() => {
    listarZonas()
      .then((datos) => {
        setZonas(datos);
        setZonaId((actual) => actual || datos[0]?.id || "");
      })
      .catch(() => setError("No se pudieron cargar las zonas"));
  }, []);

  // Trae los espacios de la zona elegida.
  const cargarEspacios = useCallback(() => {
    if (!zonaId) return;
    listarEspacios(zonaId).then(setEspacios).catch(() => setEspacios([]));
  }, [zonaId]);

  useEffect(cargarZonas, [cargarZonas]);
  useEffect(cargarEspacios, [cargarEspacios]);

  // Cada entrada o salida avisa por /ws/zonas y el mapa se refresca.
  useActualizacionesZona(() => {
    cargarZonas();
    cargarEspacios();
  });

  // Crea en la zona elegida los puestos del plano que falten.
  async function crearPuestos() {
    if (!zonaId) return;
    setProcesando(true);
    setError(null);
    setMensaje(null);
    try {
      const resultado = await crearEspaciosLote({ zona_id: zonaId, codigos: CODIGOS_PLANO });
      setMensaje(`Puestos creados: ${resultado.creados}. Ya existian: ${resultado.existentes}.`);
      cargarEspacios();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "No se pudieron crear los puestos");
    } finally {
      setProcesando(false);
    }
  }

  const zona = zonas.find((z) => z.id === zonaId);
  const creados = new Set(espacios.map((espacio) => espacio.codigo));
  const faltantes = CODIGOS_PLANO.filter((codigo) => !creados.has(codigo)).length;

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

      <div className="space-y-3 rounded-2xl bg-white p-4 shadow-sm">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <p className="text-sm text-gray-700">
            Plano: <b>{CODIGOS_PLANO.length}</b> puestos · Zona: <b>{zona?.capacidad_total ?? "—"}</b> cupos · Faltan
            por crear: <b>{faltantes}</b>
          </p>
          <Button onClick={crearPuestos} disabled={procesando || !zonaId || faltantes === 0}>
            Crear puestos del plano
          </Button>
        </div>
        {zona && zona.capacidad_total !== CODIGOS_PLANO.length && (
          <p className="rounded-xl bg-amber-100 p-3 text-sm text-amber-800">
            La capacidad de la zona ({zona.capacidad_total}) no coincide con los puestos del plano (
            {CODIGOS_PLANO.length}): el contador de cupos y el mapa no van a cuadrar.
          </p>
        )}
        {mensaje && <p className="rounded-xl bg-emerald-100 p-3 text-emerald-800">{mensaje}</p>}
        {error && <p className="rounded-xl bg-red-100 p-3 text-red-800">{error}</p>}
        <MapaParqueadero espacios={espacios} />
      </div>
    </div>
  );
}

// Las dos bitacoras: cada una vive en su microservicio y se pide y pagina por separado.
type Bitacora = "accesos" | "verificaciones";

const BITACORAS: Record<
  Bitacora,
  { etiqueta: string; tablas: string[]; listar: (filtros: FiltrosAuditoria) => Promise<AuditoriaPagina>; error: string }
> = {
  accesos: {
    etiqueta: "Accesos",
    tablas: ["accesos"],
    listar: listarAuditoria,
    error: "No se pudo cargar la auditoria de accesos: el servicio no responde.",
  },
  verificaciones: {
    etiqueta: "Verificaciones",
    tablas: ["usuarios", "vehiculos"],
    listar: listarAuditoriaVerificaciones,
    error: "No se pudo cargar la auditoria de verificaciones: el servicio no responde.",
  },
};

// Atajos de periodo de la auditoria.
type Periodo = "semestre" | "anterior" | "mes" | "quince" | "personalizado";

const AUDITORIA_POR_PAGINA = 50;

// Rango de fechas de cada atajo; en personalizado hacen falta las dos fechas.
function rangoDe(
  periodo: Periodo,
  hoy: string,
  desdeManual: string,
  hastaManual: string,
): { desde: string; hasta: string } | null {
  const actual = semestreDe(hoy);
  switch (periodo) {
    case "semestre":
      return { desde: actual.desde, hasta: actual.hasta };
    case "anterior": {
      const anterior = semestreDe(sumarDias(actual.desde, -1));
      return { desde: anterior.desde, hasta: anterior.hasta };
    }
    case "mes":
      return { desde: `${hoy.slice(0, 8)}01`, hasta: hoy };
    case "quince":
      return { desde: sumarDias(hoy, -14), hasta: hoy };
    case "personalizado":
      return desdeManual && hastaManual ? { desde: desdeManual, hasta: hastaManual } : null;
  }
}

// Auditoria de una bitacora por periodo y tabla, paginada en el servidor.
function SeccionAuditoria() {
  const [bitacora, setBitacora] = useState<Bitacora>("accesos");
  const [periodo, setPeriodo] = useState<Periodo>("semestre");
  const [desdeManual, setDesdeManual] = useState("");
  const [hastaManual, setHastaManual] = useState("");
  const [tabla, setTabla] = useState("");
  const [numeroPagina, setNumeroPagina] = useState(1);
  const [pagina, setPagina] = useState<AuditoriaPagina | null>(null);
  const [cargando, setCargando] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const hoy = hoyEnColombia();
  const semestreActual = semestreDe(hoy);
  const semestreAnterior = semestreDe(sumarDias(semestreActual.desde, -1));
  const rango = rangoDe(periodo, hoy, desdeManual, hastaManual);
  const desde = rango?.desde ?? "";
  const hasta = rango?.hasta ?? "";

  useEffect(() => {
    // Sin las dos fechas no se pide nada.
    if (!desde || !hasta) {
      setPagina(null);
      setError(null);
      setCargando(false);
      return;
    }
    // Si los filtros cambian antes de que llegue la respuesta, esa respuesta ya no se usa.
    let vigente = true;
    setCargando(true);
    setError(null);
    BITACORAS[bitacora]
      .listar({
        desde,
        hasta,
        tabla_afectada: tabla || undefined,
        pagina: numeroPagina,
        por_pagina: AUDITORIA_POR_PAGINA,
      })
      .then((resultado) => {
        if (vigente) setPagina(resultado);
      })
      .catch((err) => {
        if (!vigente) return;
        setPagina(null);
        setError(err instanceof ApiError && err.status === 422 ? err.message : BITACORAS[bitacora].error);
      })
      .finally(() => {
        if (vigente) setCargando(false);
      });
    return () => {
      vigente = false;
    };
  }, [bitacora, desde, hasta, tabla, numeroPagina]);

  // Cambiar la bitacora conserva el periodo y vuelve a todas las tablas.
  function cambiarBitacora(nueva: Bitacora) {
    setBitacora(nueva);
    setTabla("");
    setNumeroPagina(1);
  }

  // Cambiar el periodo vuelve a la primera pagina.
  function cambiarPeriodo(nuevo: Periodo) {
    setPeriodo(nuevo);
    setNumeroPagina(1);
  }

  const atajos: { valor: Periodo; etiqueta: string }[] = [
    { valor: "semestre", etiqueta: `Semestre actual (${semestreActual.nombre})` },
    { valor: "anterior", etiqueta: `Semestre anterior (${semestreAnterior.nombre})` },
    { valor: "mes", etiqueta: "Este mes" },
    { valor: "quince", etiqueta: "Últimos 15 días" },
    { valor: "personalizado", etiqueta: "Personalizado" },
  ];
  const items = pagina?.items ?? [];
  const total = pagina?.total ?? 0;
  const inicio = pagina && total > 0 ? (pagina.pagina - 1) * pagina.por_pagina + 1 : 0;
  const fin = pagina ? (pagina.pagina - 1) * pagina.por_pagina + items.length : 0;

  return (
    <div className="space-y-4">
      <div className="space-y-3 rounded-2xl bg-white p-4 shadow-sm">
        <div className="flex flex-wrap items-center gap-2">
          <span className="w-16 text-sm font-medium text-gray-700">Bitácora</span>
          {(Object.keys(BITACORAS) as Bitacora[]).map((valor) => (
            <button
              key={valor}
              onClick={() => cambiarBitacora(valor)}
              className={`rounded-full px-4 py-2 text-sm font-medium ${
                bitacora === valor ? "bg-emerald-600 text-white" : "bg-gray-100 text-gray-700"
              }`}
            >
              {BITACORAS[valor].etiqueta}
            </button>
          ))}
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <span className="w-16 text-sm font-medium text-gray-700">Periodo</span>
          {atajos.map(({ valor, etiqueta }) => (
            <button
              key={valor}
              onClick={() => cambiarPeriodo(valor)}
              className={`rounded-full px-3 py-1.5 text-sm ${
                periodo === valor ? "bg-gray-900 text-white" : "bg-gray-100 text-gray-700"
              }`}
            >
              {etiqueta}
            </button>
          ))}
        </div>

        {periodo === "personalizado" && (
          <div className="flex flex-wrap items-center gap-3 sm:pl-[4.5rem]">
            <label className="flex items-center gap-2 text-sm text-gray-700">
              Desde
              <input
                type="date"
                value={desdeManual}
                onChange={(evento) => {
                  setDesdeManual(evento.target.value);
                  setNumeroPagina(1);
                }}
                className={campo}
              />
            </label>
            <label className="flex items-center gap-2 text-sm text-gray-700">
              Hasta
              <input
                type="date"
                value={hastaManual}
                onChange={(evento) => {
                  setHastaManual(evento.target.value);
                  setNumeroPagina(1);
                }}
                className={campo}
              />
            </label>
          </div>
        )}

        <div className="flex flex-wrap items-center gap-2">
          <span className="w-16 text-sm font-medium text-gray-700">Tabla</span>
          <select
            value={tabla}
            onChange={(evento) => {
              setTabla(evento.target.value);
              setNumeroPagina(1);
            }}
            className={`${campo} flex-1 sm:flex-none`}
          >
            <option value="">Todas</option>
            {BITACORAS[bitacora].tablas.map((valor) => (
              <option key={valor} value={valor}>
                {valor}
              </option>
            ))}
          </select>
        </div>
      </div>

      {error && <p className="rounded-xl bg-red-100 p-3 text-red-800">{error}</p>}
      {!rango && <p className="text-center text-gray-400">Elige las dos fechas.</p>}
      {pagina && (
        <p className="text-sm text-gray-500">
          Del {pagina.desde} al {pagina.hasta}
        </p>
      )}

      <div className="space-y-2">
        {items.map((registro) => (
          <div key={registro.id} className="rounded-xl bg-white p-3 text-sm shadow-sm">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <p className="font-medium text-gray-900">
                {registro.tabla_afectada} · {registro.accion}
              </p>
              <p className="text-xs text-gray-500">{new Date(registro.fecha_hora).toLocaleString("es-CO")}</p>
            </div>
            {registro.motivo && <p className="mt-1 text-xs text-gray-700">Motivo: {registro.motivo}</p>}
            {registro.valores_nuevos && (
              <pre className="mt-1 overflow-x-auto text-xs text-gray-600">
                {JSON.stringify(registro.valores_nuevos)}
              </pre>
            )}
          </div>
        ))}
        {cargando && items.length === 0 && <p className="text-center text-gray-400">Cargando...</p>}
        {!cargando && pagina && items.length === 0 && (
          <p className="text-center text-gray-400">Sin registros en ese periodo.</p>
        )}
      </div>

      {pagina && (
        <div className="flex flex-wrap items-center justify-between gap-2 rounded-2xl bg-white p-4 text-sm shadow-sm">
          <span className="text-gray-500">{cargando ? "Cargando..." : `Mostrando ${inicio}–${fin} de ${total}`}</span>
          <div className="flex gap-2">
            <button
              onClick={() => setNumeroPagina(numeroPagina - 1)}
              disabled={cargando || numeroPagina <= 1}
              className="rounded-lg bg-gray-100 px-3 py-1 text-gray-700 disabled:opacity-40"
            >
              ← Anterior
            </button>
            <button
              onClick={() => setNumeroPagina(numeroPagina + 1)}
              disabled={cargando || fin >= total}
              className="rounded-lg bg-gray-100 px-3 py-1 text-gray-700 disabled:opacity-40"
            >
              Siguiente →
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
