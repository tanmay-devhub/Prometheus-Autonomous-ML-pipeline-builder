import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  darkMode: "class",
  theme: {
    extend: {
      colors: {
        ink: {
          950: "#0A0E1A", 900: "#0F1421", 850: "#141A2A", 800: "#1A2235",
          750: "#212B42", 700: "#2A364F", 600: "#3A4866", 500: "#5A6985",
          400: "#8593AD", 300: "#B4BFD4", 200: "#D6DCE8", 100: "#EEF1F7",
        },
        accent: {
          blue: "#3B82F6", blueDim: "#2563EB", blueGlow: "#60A5FA",
          emerald: "#10B981", emeraldDim: "#059669",
          amber: "#F59E0B", rose: "#F43F5E", gold: "#FBBF24", violet: "#8B5CF6",
        },
      },
      fontFamily: {
        sans: ["Inter", "ui-sans-serif", "system-ui"],
        mono: ["JetBrains Mono", "ui-monospace", "monospace"],
      },
      boxShadow: {
        "glow-blue":    "0 0 0 1px rgba(59,130,246,.4), 0 0 24px -4px rgba(59,130,246,.45)",
        "glow-emerald": "0 0 0 1px rgba(16,185,129,.4), 0 0 24px -4px rgba(16,185,129,.45)",
        "glow-gold":    "0 0 0 1px rgba(251,191,36,.5), 0 0 32px -4px rgba(251,191,36,.55)",
      },
    },
  },
  plugins: [],
};
export default config;
