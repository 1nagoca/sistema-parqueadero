/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        // Codificacion de color del mapa de cupos (ver CLAUDE-v2.md).
        cupo: {
          libre: "#22c55e",
          ocupado: "#ef4444",
          reservado: "#eab308",
          mantenimiento: "#eab308",
        },
      },
    },
  },
  plugins: [],
};
