const BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000/api/v1";
const TOKEN_KEY = "parqueadero_token";

export class ApiError extends Error {
  status: number;

  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

export function guardarToken(token: string): void {
  localStorage.setItem(TOKEN_KEY, token);
}

export function obtenerToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}

export function borrarToken(): void {
  localStorage.removeItem(TOKEN_KEY);
}

/** FastAPI devuelve `detail` como texto, o como lista de errores de validacion (422). */
export function mensajeDeDetalle(detalle: unknown): string | undefined {
  if (typeof detalle === "string") return detalle;
  if (Array.isArray(detalle)) {
    return detalle
      .map((e) => (typeof e?.msg === "string" ? e.msg.replace(/^Value error, /, "") : null))
      .filter(Boolean)
      .join(". ");
  }
  return undefined;
}

async function manejarRespuesta<T>(respuesta: Response): Promise<T> {
  if (!respuesta.ok) {
    let detalle = respuesta.statusText;
    try {
      const cuerpo = await respuesta.json();
      detalle = mensajeDeDetalle(cuerpo.detail) ?? detalle;
    } catch {
      // el cuerpo de error no era JSON; se usa el statusText
    }
    throw new ApiError(respuesta.status, detalle);
  }
  if (respuesta.status === 204) {
    return undefined as T;
  }
  return respuesta.json() as Promise<T>;
}

export async function apiGet<T>(ruta: string): Promise<T> {
  const respuesta = await fetch(`${BASE_URL}${ruta}`, {
    headers: encabezadosAuth(),
  });
  return manejarRespuesta<T>(respuesta);
}

export async function apiPost<T>(ruta: string, cuerpo?: unknown): Promise<T> {
  const respuesta = await fetch(`${BASE_URL}${ruta}`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...encabezadosAuth() },
    body: cuerpo !== undefined ? JSON.stringify(cuerpo) : undefined,
  });
  return manejarRespuesta<T>(respuesta);
}

/** Para subir archivos: el navegador fija solo el Content-Type multipart (con su boundary). */
export async function apiPostForm<T>(ruta: string, cuerpo: FormData): Promise<T> {
  const respuesta = await fetch(`${BASE_URL}${ruta}`, {
    method: "POST",
    headers: encabezadosAuth(),
    body: cuerpo,
  });
  return manejarRespuesta<T>(respuesta);
}

/** Descarga un archivo protegido (requiere Bearer, por eso no sirve un <img src> directo). */
export async function apiGetBlob(ruta: string): Promise<Blob> {
  const respuesta = await fetch(`${BASE_URL}${ruta}`, { headers: encabezadosAuth() });
  if (!respuesta.ok) {
    throw new ApiError(respuesta.status, respuesta.statusText);
  }
  return respuesta.blob();
}

function encabezadosAuth(): Record<string, string> {
  const token = obtenerToken();
  return token ? { Authorization: `Bearer ${token}` } : {};
}

export { BASE_URL };
