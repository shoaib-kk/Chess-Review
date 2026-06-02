/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        app: {
          bg: "#0b1120",
          panel: "#111827",
          panelSecondary: "#1f2937",
          border: "#263244",
          text: "#f8fafc",
          muted: "#94a3b8",
          accent: "#3b82f6",
          good: "#22c55e",
          warning: "#eab308",
          mistake: "#f97316",
          blunder: "#ef4444",
          lightSquare: "#f0d9b5",
          darkSquare: "#b58863",
        },
      },
      fontFamily: {
        sans: ["Inter", "ui-sans-serif", "system-ui", "sans-serif"],
      },
      boxShadow: {
        panel: "0 18px 50px rgba(0, 0, 0, 0.24)",
        glow: "0 0 0 1px rgba(59, 130, 246, 0.18), 0 18px 45px rgba(0, 0, 0, 0.25)",
      },
    },
  },
  plugins: [],
};
