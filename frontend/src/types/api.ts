export type RolUsuario = "estudiante" | "docente" | "administrativo" | "vigilante" | "admin";
export type TipoVehiculo = "carro" | "moto" | "bicicleta" | "otro";
export type EstadoEspacio = "libre" | "ocupado" | "reservado" | "mantenimiento";
export type TipoAcceso = "normal" | "visitante";
export type EstadoVerificacion = "pendiente" | "aprobado" | "rechazado";
export type TipoDocumento = "carnet" | "foto_placa" | "tarjeta_propiedad";
export type AccionAuditoria = "creacion" | "actualizacion" | "eliminacion";

export interface Usuario {
  id: string;
  nombre_completo: string;
  correo_institucional: string;
  documento_identidad: string;
  telefono: string | null;
  rol: RolUsuario;
  universidad: string | null;
  estado_verificacion: EstadoVerificacion;
  motivo_rechazo: string | null;
  activo: boolean;
  creado_en: string;
  actualizado_en: string;
}

export interface Vehiculo {
  id: string;
  placa: string;
  tipo_vehiculo: TipoVehiculo;
  marca: string | null;
  modelo: string | null;
  color: string | null;
  usuario_id: string | null;
  es_visitante: boolean;
  estado_verificacion: EstadoVerificacion;
  motivo_rechazo: string | null;
  creado_en: string;
}

export interface Documento {
  id: string;
  tipo: TipoDocumento;
  content_type: string;
  tamano_bytes: number;
  creado_en: string;
}

export interface VehiculoConDocumentos extends Vehiculo {
  documentos: Documento[];
}

export interface UsuarioConDocumentos extends Usuario {
  documentos: Documento[];
}

export interface SolicitudVerificacion {
  usuario: UsuarioConDocumentos;
  vehiculos: VehiculoConDocumentos[];
}

export interface RegistroEstudiantePayload {
  nombre_completo: string;
  correo_institucional: string;
  documento_identidad: string;
  telefono?: string | null;
  password: string;
  acepta_tratamiento_datos: boolean;
}

export interface Zona {
  id: string;
  nombre: string;
  ubicacion_descripcion: string | null;
  capacidad_total: number;
  cupos_disponibles: number;
  activa: boolean;
  creado_en: string;
  actualizado_en: string;
}

export interface Espacio {
  id: string;
  zona_id: string;
  codigo: string;
  estado: EstadoEspacio;
  tipo_espacio: string | null;
  creado_en: string;
  actualizado_en: string;
}

export interface Acceso {
  id: string;
  vehiculo_id: string;
  usuario_id: string | null;
  zona_id: string;
  espacio_id: string | null;
  tipo_acceso: TipoAcceso;
  fecha_hora_entrada: string;
  fecha_hora_salida: string | null;
  duracion_minutos: number | null;
  autorizado_por_id: string | null;
  justificacion: string | null;
  placa_detectada_por_alpr: boolean;
  confianza_alpr: string | null;
}

export interface AccesoActivo extends Acceso {
  placa: string;
  espacio_codigo: string | null;
}

export interface AccesoEntradaPayload {
  vehiculo_id: string;
  zona_id: string;
  espacio_id?: string | null;
  usuario_id?: string | null;
  tipo_acceso: TipoAcceso;
  autorizado_por_id?: string | null;
  justificacion?: string | null;
  placa_detectada_por_alpr?: boolean;
  confianza_alpr?: number | null;
}

export interface UsuarioCreatePayload {
  nombre_completo: string;
  correo_institucional: string;
  documento_identidad: string;
  telefono?: string | null;
  rol: RolUsuario;
  password: string;
}

export interface ZonaCreatePayload {
  nombre: string;
  ubicacion_descripcion?: string | null;
  capacidad_total: number;
}

export interface EspacioCreatePayload {
  zona_id: string;
  codigo: string;
  tipo_espacio?: string | null;
}

export interface AuditoriaAcceso {
  id: string;
  tabla_afectada: string;
  registro_id: string;
  accion: AccionAuditoria;
  valores_anteriores: Record<string, unknown> | null;
  valores_nuevos: Record<string, unknown> | null;
  realizado_por_id: string;
  motivo: string | null;
  fecha_hora: string;
  ip_origen: string | null;
}
