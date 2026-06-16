/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        app: {
          bg: "#0e0f13",
          panel: "#16181d",
          panelSecondary: "#1e2128",
          panelHover: "#262a33",
          border: "#262a31",
          borderStrong: "#333a47",
          text: "#e6e8ec",
          muted: "#9aa0aa",
          faint: "#6b7280",
          accent: "#6366f1",
          accentHover: "#5457e6",
          accentSoft: "rgba(99,102,241,0.14)",
          good: "#34d399",
          warning: "#fbbf24",
          mistake: "#fb923c",
          blunder: "#f43f5e",
          lightSquare: "#f0d9b5",
          darkSquare: "#b58863",
        },
      },
      fontFamily: {
        sans: ["Inter", "ui-sans-serif", "system-ui", "sans-serif"],
      },
      boxShadow: {
        card: "0 1px 0 0 rgba(255,255,255,0.03) inset, 0 10px 30px -16px rgba(0,0,0,0.7)",
        pop: "0 12px 40px -12px rgba(0,0,0,0.65)",
        glow: "0 0 0 1px rgba(99,102,241,0.40), 0 8px 24px -8px rgba(99,102,241,0.35)",
      },
      keyframes: {
        "fade-in": {
          from: { opacity: "0", transform: "translateY(4px)" },
          to: { opacity: "1", transform: "translateY(0)" },
        },
      },
      animation: {
        "fade-in": "fade-in 0.2s ease-out",
      },
    },
  },
  plugins: [],
};
