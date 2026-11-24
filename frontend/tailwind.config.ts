import type { Config } from "tailwindcss";

const config: Config = {
  darkMode: "class",
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}", "./lib/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        brand: {
          50: "#effcf9",
          100: "#c9f7ee",
          200: "#93efe0",
          300: "#55dfcd",
          400: "#22c6b2",
          500: "#0dab99",
          600: "#08897d",
          700: "#0a6e66",
          800: "#0c5752",
          900: "#0e4844",
          950: "#032a28",
        },
        ink: {
          50: "#f7f9fc",
          100: "#eef2f8",
          200: "#dde4ef",
          300: "#c1cddd",
          400: "#97a6bd",
          500: "#71829d",
          600: "#586781",
          700: "#48546a",
          800: "#3e4759",
          900: "#232a38",
          950: "#0b101b",
        },
      },
      fontFamily: {
        sans: [
          "Inter",
          "ui-sans-serif",
          "system-ui",
          "-apple-system",
          "Segoe UI",
          "Roboto",
          "Helvetica Neue",
          "Arial",
          "sans-serif",
        ],
        mono: ["ui-monospace", "SFMono-Regular", "Menlo", "Consolas", "monospace"],
      },
      boxShadow: {
        card: "0 1px 2px rgba(16,24,40,.04), 0 8px 24px -12px rgba(16,24,40,.10)",
        pop: "0 24px 60px -20px rgba(15,23,42,.35)",
      },
      animation: {
        "fade-up": "fadeUp .45s cubic-bezier(.22,1,.36,1) both",
        shimmer: "shimmer 1.6s linear infinite",
      },
      keyframes: {
        fadeUp: {
          from: { opacity: "0", transform: "translateY(10px)" },
          to: { opacity: "1", transform: "translateY(0)" },
        },
        shimmer: {
          "100%": { transform: "translateX(100%)" },
        },
      },
    },
  },
  plugins: [],
};

export default config;
