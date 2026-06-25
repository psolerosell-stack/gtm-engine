/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        navy: {
          950: "#0A0F1E",
          900: "#0F1629",
          800: "#1A2340",
          700: "#243158",
          600: "#2E3F70",
          500: "#3B4F88",
        },
        muted: "#8892A4",
        accent: {
          green: "#22C55E",
          blue:  "#3B82F6",
          amber: "#F59E0B",
          red:   "#EF4444",
        },
      },
      fontFamily: {
        sans: ["Inter", "ui-sans-serif", "system-ui", "sans-serif"],
      },
    },
  },
  plugins: [],
};
