// Llamadas a usuarios (servicio de identidad).
import type { Documento, Usuario, UsuarioCreatePayload } from "@/types/api";
import { apiGet, apiPost, apiPostForm } from "./client";

// El usuario de la sesion.
export function obtenerUsuarioActual(): Promise<Usuario> {
  return apiGet<Usuario>("/usuarios/me");
}

// Todos los usuarios (admin).
export function listarUsuarios(): Promise<Usuario[]> {
  return apiGet<Usuario[]>("/usuarios");
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
