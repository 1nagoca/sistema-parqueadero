// Plano del parqueadero de motos segun el dibujo del profesor: columnas con su letra, paredes, sentidos y accesos (unidades del SVG).

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

// Una flecha de sentido: va de (x1, y1) a (x2, y2).
export type Flecha = Pared;

// Un rectangulo del plano.
export interface Rectangulo {
  x: number;
  y: number;
  ancho: number;
  alto: number;
}

// Un cuadro de acceso con su texto en una o dos lineas.
export interface Caja extends Rectangulo {
  lineas: string[];
}

// Un bloque del selector con sus letras.
export interface Bloque extends Rectangulo {
  id: string;
  nombre: string;
  letras: string[];
}

// Un puesto ya ubicado en el plano.
export interface PuestoPlano {
  codigo: string;
  letra: string;
  x: number;
  y: number;
}

// Tamano total del dibujo; empieza en x=100, justo antes de la pared izquierda.
export const ANCHO = 746;
export const ALTO = 1620;
export const PLANO: Rectangulo = { x: 100, y: 0, ancho: ANCHO, alto: ALTO };

// Inicio y cantidad de las columnas del bloque de arriba y de los de abajo.
const ARRIBA = { y: 60, cantidad: 42 };
const ABAJO = { y: 768, cantidad: 46 };
// Primer y ultimo y de cada bloque, para paredes y flechas.
const ARRIBA_FIN = ARRIBA.y + ARRIBA.cantidad * PASO - (PASO - PUESTO);
const ABAJO_FIN = ABAJO.y + ABAJO.cantidad * PASO - (PASO - PUESTO);

// Columnas de arriba (A-H) y de abajo (I-V) con su x, de izquierda a derecha.
const COLUMNAS_ARRIBA: Array<[string, number]> = [
  ["A", 282],
  ["B", 332],
  ["C", 352],
  ["D", 402],
  ["E", 422],
  ["F", 492],
  ["G", 512],
  ["H", 562],
];
const COLUMNAS_ABAJO: Array<[string, number]> = [
  ["I", 142],
  ["J", 162],
  ["K", 212],
  ["L", 232],
  ["M", 282],
  ["N", 332],
  ["O", 352],
  ["P", 402],
  ["Q", 422],
  ["R", 492],
  ["S", 512],
  ["T", 562],
  ["U", 582],
  ["V", 632],
];

// Filas del fondo: W bajo abajo centro y X bajo abajo derecha, a cada lado de la via central.
const FONDO = { y: 1554, cantidad: 10 };

export const FILAS: Fila[] = [
  ...COLUMNAS_ARRIBA.map(([letra, x]) => ({ letra, vertical: true, tramos: [{ x, y: ARRIBA.y, cantidad: ARRIBA.cantidad }] })),
  ...COLUMNAS_ABAJO.map(([letra, x]) => ({ letra, vertical: true, tramos: [{ x, y: ABAJO.y, cantidad: ABAJO.cantidad }] })),
  { letra: "W", tramos: [{ x: 278, y: FONDO.y, cantidad: FONDO.cantidad }] },
  { letra: "X", tramos: [{ x: 490, y: FONDO.y, cantidad: FONDO.cantidad }] },
];

// Pared vertical en x de arriba abajo.
function vertical(x: number, y1: number, y2: number): Pared {
  return { x1: x, y1, x2: x, y2 };
}

export const PAREDES: Pared[] = [
  // Encima de todo el bloque de arriba.
  { x1: 272, y1: 10, x2: 586, y2: 10 },
  // Bloque de arriba: | A B | C D | E   F | G H |
  ...[279, 349, 419, 509, 579].map((x) => vertical(x, ARRIBA.y - 10, ARRIBA_FIN + 4)),
  // Encima de abajo izquierda y abajo centro, y encima de R-U (la entrada queda abierta sobre U-V).
  { x1: 109, y1: 748, x2: 436, y2: 748 },
  { x1: 486, y1: 748, x2: 596, y2: 748 },
  // Pared izquierda de todo el bloque de abajo.
  vertical(109, 748, ABAJO_FIN + 4),
  // Bloques de abajo: I | J, K | L, | M, N | O, P | Q, R | S, T | U, V |
  ...[159, 229, 279, 349, 419, 509, 579, 649].map((x) => vertical(x, ABAJO.y - 10, ABAJO_FIN + 4)),
  // Debajo de las filas del fondo.
  { x1: 278, y1: 1574, x2: 436, y2: 1574 },
  { x1: 490, y1: 1574, x2: 648, y2: 1574 },
];

// Pasillo entre dos bordes: baja por su tercio izquierdo y sube por su tercio derecho.
function pasillo(izquierda: number, derecha: number, arriba: number, abajo: number): Flecha[] {
  const tercio = (derecha - izquierda) / 3;
  return [
    { x1: izquierda + tercio, y1: arriba + 4, x2: izquierda + tercio, y2: abajo - 4 },
    { x1: derecha - tercio, y1: abajo - 4, x2: derecha - tercio, y2: arriba + 4 },
  ];
}

export const FLECHAS: Flecha[] = [
  // Via de arriba: a la derecha y de vuelta a la izquierda.
  { x1: 286, y1: 24, x2: 582, y2: 24 },
  { x1: 582, y1: 38, x2: 286, y2: 38 },
  // Via central: baja hasta la entrada y salida y sube de vuelta.
  { x1: 455, y1: 24, x2: 455, y2: 1580 },
  { x1: 473, y1: 1580, x2: 473, y2: 30 },
  // Pasillos del bloque de arriba: A-B, C-D, G-H.
  ...pasillo(296, 332, ARRIBA.y, ARRIBA_FIN),
  ...pasillo(366, 402, ARRIBA.y, ARRIBA_FIN),
  ...pasillo(526, 562, ARRIBA.y, ARRIBA_FIN),
  // Pasillos de abajo: pared-I, J-K, L-pared, M-N, O-P, S-T, U-V.
  ...pasillo(109, 142, ABAJO.y, ABAJO_FIN),
  ...pasillo(176, 212, ABAJO.y, ABAJO_FIN),
  ...pasillo(246, 279, ABAJO.y, ABAJO_FIN),
  ...pasillo(296, 332, ABAJO.y, ABAJO_FIN),
  ...pasillo(366, 402, ABAJO.y, ABAJO_FIN),
  ...pasillo(526, 562, ABAJO.y, ABAJO_FIN),
  ...pasillo(596, 632, ABAJO.y, ABAJO_FIN),
  // Via de abajo, de la pared izquierda a la pared de V: a la izquierda y de vuelta a la derecha.
  { x1: 649, y1: 1522, x2: 109, y2: 1522 },
  { x1: 109, y1: 1538, x2: 649, y2: 1538 },
];

// Cuadros de entrada y salida (al final de la via central) y de entrada a la universidad (a la derecha).
export const ENTRADA_SALIDA: Caja = { x: 404, y: 1582, ancho: 120, alto: 28, lineas: ["Entrada y salida"] };
export const ENTRADA_UNIVERSIDAD: Caja = { x: 690, y: 680, ancho: 150, alto: 52, lineas: ["Entrada", "a la universidad"] };
export const CAJAS: Caja[] = [ENTRADA_SALIDA, ENTRADA_UNIVERSIDAD];
// Camino punteado desde el pasillo U-V hasta la entrada a la universidad.
export const CAMINO_UNIVERSIDAD = "M 620 764 V 714 Q 620 706 628 706 H 686";

// Bloques del selector con su rectangulo en el plano.
export const BLOQUES: Bloque[] = [
  { id: "arriba-izquierda", nombre: "Arriba izquierda", letras: ["A", "B", "C", "D", "E"], x: 272, y: 42, ancho: 168, alto: 696 },
  { id: "arriba-derecha", nombre: "Arriba derecha", letras: ["F", "G", "H"], x: 486, y: 42, ancho: 100, alto: 696 },
  { id: "abajo-izquierda", nombre: "Abajo izquierda", letras: ["I", "J", "K", "L"], x: 104, y: 742, ancho: 168, alto: 768 },
  { id: "abajo-centro", nombre: "Abajo centro", letras: ["M", "N", "O", "P", "Q"], x: 272, y: 742, ancho: 168, alto: 768 },
  { id: "abajo-derecha", nombre: "Abajo derecha", letras: ["R", "S", "T", "U", "V"], x: 486, y: 742, ancho: 170, alto: 768 },
  { id: "fondo", nombre: "Fondo", letras: ["W", "X"], x: 260, y: 1544, ancho: 396, alto: 70 },
];

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
