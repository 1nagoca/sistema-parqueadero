// Frases en espanol para las trazas de las tres bitacoras de auditoria.
import type { AuditoriaAcceso, DetalleAcceso, DetalleVerificacion } from "@/types/api";

// Nombres que el panel ya resolvio: de quien registro (por id) y de cada zona (por id).
export interface NombresAuditoria {
  usuarios: Record<string, string | null>;
  zonas: Record<string, string>;
}

// Frase de una traza; null si no hay datos para escribirla (el panel muestra el JSON).
export function fraseDeTraza(traza: AuditoriaAcceso, nombres: NombresAuditoria): string | null {
  switch (traza.tabla_afectada) {
    case "accesos":
      return fraseDeAcceso(traza, nombres.usuarios[traza.realizado_por_id] ?? null, nombres.zonas);
    case "cierre_semestre":
      return fraseDeCierre(traza, nombres.usuarios[traza.realizado_por_id] ?? null);
    case "usuarios":
      return fraseDeUsuario(traza, traza.realizado_por_nombre ?? null);
    case "vehiculos":
      return fraseDeVehiculo(traza, traza.realizado_por_nombre ?? null);
    case "espacios":
      return fraseDeMantenimiento(traza, nombres.usuarios[traza.realizado_por_id] ?? null, nombres.zonas);
    default:
      return null;
  }
}

// Cierra la frase con quien la hizo, o solo con el punto si no se sabe.
function conAutor(frase: string, autor: string | null, union: string): string {
  return autor ? `${frase}${union}${autor}.` : `${frase}.`;
}

// 1 minuto, 4 minutos o 1 h 05 min.
function duracion(minutos: number): string {
  if (minutos < 60) return minutos === 1 ? "1 minuto" : `${minutos} minutos`;
  return `${Math.floor(minutos / 60)} h ${String(minutos % 60).padStart(2, "0")} min`;
}

// 1 acceso, 3 accesos.
function plural(cantidad: number, palabra: string): string {
  return `${cantidad} ${palabra}${cantidad === 1 ? "" : "s"}`;
}

// Entrada o salida de una moto, con puesto, zona y duracion si se conocen.
function fraseDeAcceso(traza: AuditoriaAcceso, autor: string | null, zonas: Record<string, string>): string | null {
  const detalle = traza.detalle as DetalleAcceso | null | undefined;
  if (!detalle) return null;
  if (traza.accion === "creacion") {
    const visitante = detalle.tipo_acceso === "visitante" ? " (visitante)" : "";
    const zona = zonas[detalle.zona_id];
    let destino = "";
    if (detalle.espacio_codigo) destino = ` al puesto ${detalle.espacio_codigo}${zona ? ` de ${zona}` : ""}`;
    else if (zona) destino = ` a ${zona}`;
    return conAutor(`Entrada de la moto ${detalle.placa}${visitante}${destino}`, autor, ", registrada por ");
  }
  if (traza.accion === "actualizacion") {
    const tras = detalle.duracion_minutos != null ? ` tras ${duracion(detalle.duracion_minutos)}` : "";
    return conAutor(`Salida de la moto ${detalle.placa}${tras}`, autor, ", registrada por ");
  }
  return null;
}

// Cierre de semestre con lo que se archivo y la fecha de corte.
function fraseDeCierre(traza: AuditoriaAcceso, autor: string | null): string | null {
  const valores: Record<string, unknown> = traza.valores_nuevos ?? {};
  const { accesos, trazas, corte } = valores;
  if (typeof accesos !== "number" || typeof trazas !== "number" || typeof corte !== "string") return null;
  const fecha = new Date(`${corte}T00:00:00Z`);
  const textoCorte = Number.isNaN(fecha.getTime())
    ? corte
    : fecha.toLocaleDateString("es-CO", { day: "numeric", month: "long", year: "numeric", timeZone: "UTC" });
  return conAutor(
    `Cierre de semestre: se archivaron ${plural(accesos, "acceso")} y ${plural(trazas, "traza")} anteriores al ${textoCorte}`,
    autor,
    ", por ",
  );
}

// Aprobacion, rechazo, baja o reactivacion de un usuario.
function fraseDeUsuario(traza: AuditoriaAcceso, autor: string | null): string | null {
  const detalle = traza.detalle as DetalleVerificacion | null | undefined;
  const valores = traza.valores_nuevos;
  if (!detalle?.nombre || !valores) return null;
  const quien = detalle.rol ? `${detalle.nombre} (${detalle.rol})` : detalle.nombre;
  if (valores.activo === false) return conAutor(`Baja de ${quien}`, autor, " por ");
  if (valores.activo === true) {
    const pendiente = valores.estado_verificacion === "pendiente" ? "; vuelve a pendiente" : "";
    return `Reactivación de ${quien}${autor ? ` por ${autor}` : ""}${pendiente}.`;
  }
  const estado = valores.estado_verificacion;
  if (estado !== "aprobado" && estado !== "rechazado") return null;
  return conAutor(`${quien} ${estado}`, autor, " por ");
}

// Aprobacion o rechazo de una moto, con su dueno o como visitante.
function fraseDeVehiculo(traza: AuditoriaAcceso, autor: string | null): string | null {
  const detalle = traza.detalle as DetalleVerificacion | null | undefined;
  const estado = traza.valores_nuevos?.estado_verificacion;
  if (!detalle?.placa || (estado !== "aprobado" && estado !== "rechazado")) return null;
  const dueno = detalle.nombre ? ` de ${detalle.nombre}` : " (visitante)";
  return conAutor(`Moto ${detalle.placa}${dueno} ${estado === "aprobado" ? "aprobada" : "rechazada"}`, autor, " por ");
}

// Un puesto que entra en mantenimiento (con su motivo) o que se habilita (con cuanto duro).
function fraseDeMantenimiento(
  traza: AuditoriaAcceso,
  autor: string | null,
  zonas: Record<string, string>,
): string | null {
  const nuevos: Record<string, unknown> = traza.valores_nuevos ?? {};
  const { codigo, zona, zona_id: zonaId, estado, motivo } = nuevos;
  if (typeof codigo !== "string") return null;
  const nombreZona = typeof zona === "string" ? zona : typeof zonaId === "string" ? zonas[zonaId] : undefined;
  const puesto = `Puesto ${codigo}${nombreZona ? ` de ${nombreZona}` : ""}`;
  if (estado === "mantenimiento") {
    if (typeof motivo !== "string") return null;
    return conAutor(`${puesto} en mantenimiento: ${motivo}`, autor, ", por ");
  }
  if (estado === "libre") {
    const minutos = minutosEntre(traza.valores_anteriores?.inicio, nuevos.fin);
    const tras = minutos != null ? ` tras ${duracion(minutos)}` : "";
    return conAutor(`${puesto} habilitado${tras}`, autor, ", por ");
  }
  return null;
}

// Minutos redondeados entre dos fechas ISO; null si falta alguna o no se entiende.
function minutosEntre(desde: unknown, hasta: unknown): number | null {
  if (typeof desde !== "string" || typeof hasta !== "string") return null;
  const diferencia = new Date(hasta).getTime() - new Date(desde).getTime();
  return Number.isNaN(diferencia) || diferencia < 0 ? null : Math.round(diferencia / 60000);
}
