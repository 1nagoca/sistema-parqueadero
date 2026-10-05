import { apiPostForm } from "./client";

export interface LecturaPlaca {
  placa: string;
  /** Entre 0 y 1. */
  confianza: number;
}

/** Envia la foto al microservicio de vision (ALPR) a traves del gateway. */
export function reconocerPlaca(imagen: File): Promise<LecturaPlaca> {
  const cuerpo = new FormData();
  cuerpo.append("imagen", imagen);
  return apiPostForm<LecturaPlaca>("/alpr/reconocer", cuerpo);
}
