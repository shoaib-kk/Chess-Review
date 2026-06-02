/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        app: {
          bg: "#0f172a",
          panel: "#1e293b",
          accent: "#3b82f6",
          lightSquare: "#f0d9b5",
          darkSquare: "#b58863",
        },
      },
      fontFamily: {
        sans: ["Inter", "ui-sans-serif", "system-ui", "sans-serif"],
      },
      boxShadow: {
        panel: "0 18px 45px rgba(2, 6, 23, 0.35)",
      },
    },
  },
  plugins: [],
};
