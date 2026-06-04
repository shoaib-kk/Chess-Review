/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        app: {
          bg: "#181818",
          panel: "#1f1f1f",
          panelSecondary: "#2a2a2a",
          border: "#343434",
          text: "#d4d4d4",
          muted: "#8a8a8a",
          accent: "#007acc",
          good: "#89d185",
          warning: "#dcdcaa",
          mistake: "#ce9178",
          blunder: "#f14c4c",
          lightSquare: "#f0d9b5",
          darkSquare: "#b58863",
        },
      },
      fontFamily: {
        sans: ["Inter", "ui-sans-serif", "system-ui", "sans-serif"],
      },
    },
  },
  plugins: [],
};
