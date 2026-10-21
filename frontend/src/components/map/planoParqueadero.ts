// Plano del parqueadero de motos: filas con su letra, paredes, entrada y salida (unidades del SVG).

// Medidas de cada puesto y separacion entre puestos.
export const PUESTO = 14;
export const PASO = 16;

// Un tramo de puestos seguidos que empieza en (x, y).
export interface Tramo {
  x: number;
  y: number;
  cantidad: number;
}

// Una fila con su letra; los puestos se numeran seguidos a traves de sus tramos.
export interface Fila {
  letra: string;
  vertical?: boolean;
  tramos: Tramo[];
}

// Una pared como linea recta.
export interface Pared {
  x1: number;
  y1: number;
  x2: number;
  y2: number;
}

// Un puesto ya ubicado en el plano.
export interface PuestoPlano {
  codigo: string;
  letra: string;
  x: number;
  y: number;
}

// Tamano total del dibujo.
export const ANCHO = 1170;
export const ALTO = 380;

// Filas del bloque izquierdo (C a K, 30 puestos cada una) en parejas separadas por pared.
const FILAS_IZQUIERDA: Array<[string, number]> = [
  ["C", 70],
  ["D", 106],
  ["E", 128],
  ["F", 170],
  ["G", 192],
  ["H", 250],
  ["I", 272],
  ["J", 310],
  ["K", 332],
];

// Filas del bloque derecho (L a Q, dos tramos de 15) en parejas separadas por pared.
const FILAS_DERECHA: Array<[string, number]> = [
  ["L", 80],
  ["M", 102],
  ["N", 150],
  ["O", 172],
  ["P", 226],
  ["Q", 248],
];

export const FILAS: Fila[] = [
  {
    letra: "A",
    vertical: true,
    tramos: [
      { x: 78, y: 26, cantidad: 7 },
      { x: 78, y: 150, cantidad: 4 },
      { x: 78, y: 250, cantidad: 7 },
    ],
  },
  {
    letra: "B",
    tramos: [
      { x: 110, y: 30, cantidad: 15 },
      { x: 360, y: 30, cantidad: 17 },
    ],
  },
  ...FILAS_IZQUIERDA.map(([letra, y]) => ({ letra, tramos: [{ x: 110, y, cantidad: 30 }] })),
  ...FILAS_DERECHA.map(([letra, y]) => ({
    letra,
    tramos: [
      { x: 662, y, cantidad: 15 },
      { x: 918, y, cantidad: 15 },
    ],
  })),
];

export const PAREDES: Pared[] = [
  // Pared izquierda, abierta en la entrada.
  { x1: 70, y1: 20, x2: 70, y2: 216 },
  { x1: 70, y1: 248, x2: 70, y2: 366 },
  // Encima de la fila B (dos tramos) y de la fila C.
  { x1: 106, y1: 24, x2: 350, y2: 24 },
  { x1: 356, y1: 24, x2: 632, y2: 24 },
  { x1: 104, y1: 64, x2: 594, y2: 64 },
  // Entre las parejas del bloque izquierdo.
  { x1: 104, y1: 124, x2: 594, y2: 124 },
  { x1: 104, y1: 188, x2: 594, y2: 188 },
  { x1: 104, y1: 268, x2: 594, y2: 268 },
  { x1: 104, y1: 328, x2: 594, y2: 328 },
  // Entre las parejas del bloque derecho.
  { x1: 656, y1: 98, x2: 1162, y2: 98 },
  { x1: 656, y1: 168, x2: 1162, y2: 168 },
  { x1: 656, y1: 244, x2: 1162, y2: 244 },
  // Muro junto a la salida de estudiantes.
  { x1: 640, y1: 312, x2: 640, y2: 370 },
];

// Cuadro de la entrada (a la izquierda) y de la salida de estudiantes (abajo a la derecha).
export const ENTRADA = { x: 4, y: 220, ancho: 62, alto: 26, texto: "Entrada" };
export const SALIDA = { x: 740, y: 330, ancho: 190, alto: 30, texto: "Salida de estudiantes" };
// Puerta de la salida: arco desde el muro.
export const PUERTA = "M 640 314 A 52 52 0 0 1 692 366";

// Codigo de un puesto: letra y numero de dos digitos (B-07).
export function codigoPuesto(letra: string, numero: number): string {
  return `${letra}-${String(numero).padStart(2, "0")}`;
}

// Todos los puestos del plano con su posicion, en orden.
export const PUESTOS: PuestoPlano[] = FILAS.flatMap((fila) => {
  let numero = 0;
  return fila.tramos.flatMap((tramo) =>
    Array.from({ length: tramo.cantidad }, (_, indice) => {
      numero += 1;
      return {
        codigo: codigoPuesto(fila.letra, numero),
        letra: fila.letra,
        x: fila.vertical ? tramo.x : tramo.x + indice * PASO,
        y: fila.vertical ? tramo.y + indice * PASO : tramo.y,
      };
    }),
  );
});

// Codigos de todos los puestos, para crearlos en el backend.
export const CODIGOS_PLANO = PUESTOS.map((puesto) => puesto.codigo);
