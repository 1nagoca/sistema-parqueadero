// Llamadas a usuarios (servicio de identidad).
import type { Documento, FiltrosUsuarios, Usuario, UsuarioCreatePayload, UsuariosPagina } from "@/types/api";
import { apiGet, apiPost, apiPostForm } from "./client";

// El usuario de la sesion.
export function obtenerUsuarioActual(): Promise<Usuario> {
  return apiGet<Usuario>("/usuarios/me");
}

// Una pagina de usuarios con buscador y filtros (admin).
export function listarUsuarios(filtros: FiltrosUsuarios = {}): Promise<UsuariosPagina> {
  const params = new URLSearchParams();
  if (filtros.pagina) params.set("pagina", String(filtros.pagina));
  if (filtros.por_pagina) params.set("por_pagina", String(filtros.por_pagina));
  if (filtros.buscar?.trim()) params.set("buscar", filtros.buscar.trim());
  if (filtros.rol) params.set("rol", filtros.rol);
  if (filtros.activo !== undefined) params.set("activo", String(filtros.activo));
  const query = params.toString();
  return apiGet<UsuariosPagina>(`/usuarios${query ? `?${query}` : ""}`);
}

// Da de baja a un estudiante o vigilante con un motivo (admin).
export function darDeBajaUsuario(id: string, motivo: string): Promise<Usuario> {
  return apiPost<Usuario>(`/usuarios/${id}/desactivar`, { motivo });
}

// Reactiva a un usuario dado de baja (admin).
export function reactivarUsuario(id: string): Promise<Usuario> {
  return apiPost<Usuario>(`/usuarios/${id}/reactivar`);
}

// Crea un usuario que no es estudiante (admin).
export function crearUsuario(datos: UsuarioCreatePayload): Promise<Usuario> {
  return apiPost<Usuario>("/usuarios", datos);
}

// El estudiante sube su carnet.
export function subirCarnet(archivo: File): Promise<Usuario> {
  const formulario = new FormData();
  formulario.append("archivo", archivo);
  return apiPostForm<Usuario>("/usuarios/me/carnet", formulario);
}

// El carnet que ya subio el estudiante.
export function listarMisDocumentos(): Promise<Documento[]> {
  return apiGet<Documento[]>("/usuarios/me/documentos");
}
