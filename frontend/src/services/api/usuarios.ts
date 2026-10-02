import type { Documento, Usuario, UsuarioCreatePayload } from "@/types/api";
import { apiGet, apiPost, apiPostForm } from "./client";

export function obtenerUsuarioActual(): Promise<Usuario> {
  return apiGet<Usuario>("/usuarios/me");
}

export function listarUsuarios(): Promise<Usuario[]> {
  return apiGet<Usuario[]>("/usuarios");
}

export function crearUsuario(datos: UsuarioCreatePayload): Promise<Usuario> {
  return apiPost<Usuario>("/usuarios", datos);
}

export function subirCarnet(archivo: File): Promise<Usuario> {
  const formulario = new FormData();
  formulario.append("archivo", archivo);
  return apiPostForm<Usuario>("/usuarios/me/carnet", formulario);
}

export function listarMisDocumentos(): Promise<Documento[]> {
  return apiGet<Documento[]>("/usuarios/me/documentos");
}
