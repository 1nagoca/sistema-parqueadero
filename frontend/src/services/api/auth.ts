import { BASE_URL, ApiError } from "./client";

export interface TokenRespuesta {
  access_token: string;
  token_type: string;
}

export async function login(correo: string, password: string): Promise<TokenRespuesta> {
  const cuerpo = new URLSearchParams();
  cuerpo.set("username", correo);
  cuerpo.set("password", password);

  const respuesta = await fetch(`${BASE_URL}/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: cuerpo.toString(),
  });

  if (!respuesta.ok) {
    const cuerpoError = await respuesta.json().catch(() => ({}));
    throw new ApiError(respuesta.status, cuerpoError.detail ?? "No se pudo iniciar sesion");
  }
  return respuesta.json();
}
