import type { RolUsuario } from "@/types/api";

/** A donde aterriza cada rol despues de iniciar sesion. */
export function rutaInicioPara(rol: RolUsuario): string {
  if (rol === "admin") return "/admin";
  if (rol === "vigilante") return "/vigilante";
  return "/mapa";
}
