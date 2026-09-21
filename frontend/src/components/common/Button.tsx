import type { ButtonHTMLAttributes } from "react";

type Variante = "primaria" | "peligro" | "secundaria";

interface Props extends ButtonHTMLAttributes<HTMLButtonElement> {
  variante?: Variante;
}

const clasesPorVariante: Record<Variante, string> = {
  primaria: "bg-emerald-600 hover:bg-emerald-700 text-white",
  peligro: "bg-red-600 hover:bg-red-700 text-white",
  secundaria: "bg-gray-200 hover:bg-gray-300 text-gray-900",
};

/** Botón táctil grande, pensado para el panel de vigilancia (uso mobile-first en el punto de acceso). */
export default function Button({ variante = "primaria", className = "", ...props }: Props) {
  return (
    <button
      className={`min-h-14 rounded-xl px-6 py-3 text-lg font-semibold transition-colors disabled:cursor-not-allowed disabled:opacity-50 ${clasesPorVariante[variante]} ${className}`}
      {...props}
    />
  );
}
