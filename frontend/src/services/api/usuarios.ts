import type { Usuario, UsuarioCreatePayload } from "@/types/api";
import { apiGet, apiPost } from "./client";

export function obtenerUsuarioActual(): Promise<Usuario> {
  return apiGet<Usuario>("/usuarios/me");
}

export function listarUsuarios(): Promise<Usuario[]> {
  return apiGet<Usuario[]>("/usuarios");
}

export function crearUsuario(datos: UsuarioCreatePayload): Promise<Usuario> {
  return apiPost<Usuario>("/usuarios", datos);
}
