/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./templates/**/*.html",
    "./static/**/*.js",
  ],
  theme: {
    extend: {
      colors: {
        // Colores inspirados en verdes mexicanos
        'verde-mexicano-oscuro': '#006B3D', // Un verde botella o pino oscuro
        'verde-mexicano-medio': '#008542', // Un verde más vibrante
        'verde-mexicano-claro': '#78BB42', // Un verde más claro, casi limón
        'rojo-mexicano': '#BF0A30',      // Un rojo intenso
        'blanco-mexicano': '#FFFFFF',    // Blanco puro
      },
    },
  },
  plugins: [],
}