/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        app: {
          // Warm near-black page base, then a layered elevation ladder. Each
          // surface steps up with a faint warmth so depth reads without relying
          // on heavy borders. Cards sit on `surface`; raised chrome on `raised`.
          bg: "#0a0a0c",
          bgInset: "#0d0d10",
          surface: "#121316",
          raised: "#191a1e",
          raisedHover: "#212329",
          overlay: "#1c1d22",
          // Legacy aliases (pre-redesign pages still reference these). They map
          // onto the new elevation ladder so older components keep rendering
          // until each page is migrated.
          panel: "#121316",
          panelSecondary: "#191a1e",
          panelHover: "#212329",
          // Hairline borders. `border` is barely above the surface fill so cards
          // read as quiet edges; `borderStrong` carries hover/focus affordance.
          border: "#222328",
          borderStrong: "#34363d",
          text: "#f3f3f5",
          muted: "#9b9ca6",
          faint: "#71727c",
          subtle: "#85868f",
          // Single warm gold accent, used sparingly. `accentFg` is the dark ink
          // that sits on gold fills (white fails contrast on gold).
          accent: "#c8a15a",
          accentHover: "#d9b66e",
          accentFg: "#1a1404",
          accentSoft: "rgba(200,161,90,0.12)",
          accentLine: "rgba(200,161,90,0.30)",
          // Semantic move/result hues — kept from the analysis design language.
          good: "#5cb585",
          warning: "#d6b24a",
          mistake: "#dc8a45",
          blunder: "#dd5b52",
          brilliant: "#34c9bb",
          loss: "#dd5b52",
          draw: "#9b9ca6",
          lightSquare: "#ebecd0",
          darkSquare: "#739552",
        },
      },
      fontFamily: {
        sans: ["Inter", "ui-sans-serif", "system-ui", "sans-serif"],
        mono: ["'JetBrains Mono'", "ui-monospace", "SFMono-Regular", "monospace"],
      },
      letterSpacing: {
        tightest: "-0.03em",
      },
      borderRadius: {
        "2xl": "1rem",
        "3xl": "1.375rem",
      },
      boxShadow: {
        // Layered elevation. Soft, never oversized; no coloured glows by default.
        card: "0 1px 2px 0 rgba(0,0,0,0.35)",
        raised: "0 2px 8px -2px rgba(0,0,0,0.45), 0 1px 2px 0 rgba(0,0,0,0.3)",
        lift: "0 14px 40px -18px rgba(0,0,0,0.7), 0 2px 8px -4px rgba(0,0,0,0.5)",
        pop: "0 16px 48px -16px rgba(0,0,0,0.7)",
        // Faint inner top highlight so surfaces catch a hint of light.
        sheen: "inset 0 1px 0 0 rgba(255,255,255,0.04)",
        accent: "0 0 0 1px rgba(200,161,90,0.4), 0 8px 28px -12px rgba(200,161,90,0.35)",
      },
      backgroundImage: {
        // Subtle, never neon. A faint vertical warmth and surface sheens.
        "app-radial":
          "radial-gradient(1200px 600px at 78% -8%, rgba(200,161,90,0.06), transparent 60%), radial-gradient(900px 500px at 8% 4%, rgba(120,130,160,0.045), transparent 55%)",
        "surface-sheen":
          "linear-gradient(180deg, rgba(255,255,255,0.035), rgba(255,255,255,0) 38%)",
        "accent-sheen":
          "linear-gradient(135deg, rgba(200,161,90,0.16), rgba(200,161,90,0.04) 55%, rgba(200,161,90,0) 100%)",
        "hairline-x":
          "linear-gradient(90deg, transparent, rgba(255,255,255,0.08), transparent)",
      },
      keyframes: {
        "fade-in": {
          from: { opacity: "0", transform: "translateY(4px)" },
          to: { opacity: "1", transform: "translateY(0)" },
        },
        rise: {
          from: { opacity: "0", transform: "translateY(10px)" },
          to: { opacity: "1", transform: "translateY(0)" },
        },
        "pop-in": {
          from: { opacity: "0", transform: "scale(0.96)" },
          to: { opacity: "1", transform: "scale(1)" },
        },
        shimmer: {
          "100%": { transform: "translateX(100%)" },
        },
        "ring-pulse": {
          "0%, 100%": { opacity: "1" },
          "50%": { opacity: "0.55" },
        },
      },
      animation: {
        "fade-in": "fade-in 0.2s ease-out",
        rise: "rise 0.4s cubic-bezier(0.22, 1, 0.36, 1) both",
        "pop-in": "pop-in 0.25s cubic-bezier(0.22, 1, 0.36, 1) both",
        shimmer: "shimmer 1.6s infinite",
        "ring-pulse": "ring-pulse 2s ease-in-out infinite",
      },
      transitionTimingFunction: {
        spring: "cubic-bezier(0.22, 1, 0.36, 1)",
      },
    },
  },
  plugins: [],
};
