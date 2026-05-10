import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./app/**/*.{ts,tsx}",
    "./components/**/*.{ts,tsx}",
    "./lib/**/*.{ts,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        primary: {
          DEFAULT: "#7B2CBF",
          50: "#1a0f2e",
          100: "#231340",
          200: "#3a1d6e",
          300: "#5a2d9e",
          400: "#6d2db5",
          500: "#7B2CBF",
          600: "#9340df",
          700: "#a85eea",
          800: "#c48ef2",
          900: "#e0c4f9",
        },
        accent: {
          DEFAULT: "#FF1493",
          50: "#2d0a1e",
          100: "#4a0f30",
          200: "#7a1850",
          300: "#b82075",
          400: "#e01688",
          500: "#FF1493",
          600: "#ff3da6",
          700: "#ff6bba",
          800: "#ff99d0",
          900: "#ffcce8",
        },
        ink: {
          DEFAULT: "#ffffff",
          muted: "#94909e",
          subtle: "#5c5869",
        },
        surface: {
          DEFAULT: "#14141f",
          alt: "#0a0a0f",
          elevated: "#1a1a28",
        },
        border: {
          DEFAULT: "rgba(255,255,255,0.08)",
          strong: "rgba(255,255,255,0.14)",
        },
      },
      fontFamily: {
        sans: ["var(--font-inter)", "ui-sans-serif", "system-ui", "sans-serif"],
        display: ["var(--font-display)", "ui-sans-serif", "sans-serif"],
      },
      backgroundImage: {
        "gradient-brand":
          "linear-gradient(135deg, #FF1493 0%, #7B2CBF 50%, #5C1F95 100%)",
        "gradient-soft":
          "linear-gradient(135deg, rgba(255,20,147,0.1) 0%, rgba(123,44,191,0.08) 50%, rgba(92,31,149,0.06) 100%)",
        "gradient-subtle":
          "linear-gradient(180deg, #14141f 0%, #0a0a0f 100%)",
      },
      boxShadow: {
        brand: "0 16px 40px -12px rgba(123, 44, 191, 0.4)",
        "brand-soft": "0 8px 24px -8px rgba(255, 20, 147, 0.2)",
        card: "0 1px 3px rgba(0,0,0,0.3), 0 8px 24px -12px rgba(0,0,0,0.4)",
      },
      borderRadius: {
        xl: "0.875rem",
        "2xl": "1.25rem",
        "3xl": "1.75rem",
      },
      keyframes: {
        "fade-in": {
          from: { opacity: "0", transform: "translateY(4px)" },
          to: { opacity: "1", transform: "translateY(0)" },
        },
        shimmer: {
          "0%": { backgroundPosition: "-200% 0" },
          "100%": { backgroundPosition: "200% 0" },
        },
        "pulse-soft": {
          "0%, 100%": { opacity: "1" },
          "50%": { opacity: "0.5" },
        },
        float: {
          "0%, 100%": { transform: "translateY(0px)" },
          "50%": { transform: "translateY(-10px)" },
        },
        "kb-zoom-in": {
          "0%": { transform: "scale(1) translate(0, 0)" },
          "100%": { transform: "scale(1.15) translate(-2%, -1%)" },
        },
        "kb-zoom-out": {
          "0%": { transform: "scale(1.18) translate(-2%, -2%)" },
          "100%": { transform: "scale(1) translate(0, 0)" },
        },
        "kb-slide-left": {
          "0%": { transform: "scale(1.08) translate(3%, 0)" },
          "100%": { transform: "scale(1.12) translate(-3%, -1%)" },
        },
        "kb-slide-right": {
          "0%": { transform: "scale(1.08) translate(-3%, 0)" },
          "100%": { transform: "scale(1.12) translate(3%, 1%)" },
        },
      },
      animation: {
        "fade-in": "fade-in 0.3s ease-out",
        shimmer: "shimmer 2s linear infinite",
        "pulse-soft": "pulse-soft 2.5s cubic-bezier(0.4,0,0.6,1) infinite",
        float: "float 6s ease-in-out infinite",
        "kb-zoom-in": "kb-zoom-in 5s ease-out forwards",
        "kb-zoom-out": "kb-zoom-out 5s ease-out forwards",
        "kb-slide-left": "kb-slide-left 5s ease-out forwards",
        "kb-slide-right": "kb-slide-right 5s ease-out forwards",
      },
    },
  },
  plugins: [require("tailwindcss-animate")],
};

export default config;
