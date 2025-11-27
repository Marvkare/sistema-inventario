
/** @type {import('tailwindcss').Config} */
module.exports = {
  // IMPORTANTE: Esto le dice a Tailwind que busque clases dentro de la carpeta templates
  content: [
    "./templates/**/*.html",
    "./static/**/*.js" 
  ],
  theme: {
    extend: {},
  },
  plugins: [],
}