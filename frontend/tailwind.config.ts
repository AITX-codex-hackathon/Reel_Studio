import type { Config } from "tailwindcss";

const config: Config = {
  darkMode: "class",
  content: [
    "./app/**/*.{ts,tsx}",
    "./components/**/*.{ts,tsx}",
    "./lib/**/*.{ts,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        // Pink / purple / white palette
        primary: {
          DEFAULT: "#7B2CBF", // deep purple
          50: "#F6F0FB",
          100: "#EDE0F7",
          200: "#D7B8EE",
          300: "#BC8FE2",
          400: "#9D5BD2",
          500: "#7B2CBF",
          600: "#6322A0",
          700: "#4C197A",
          800: "#36115A",
          900: "#220A3A",
        },
        accent: {
          DEFAULT: "#FF1493", // hot pink
          50: "#FFE9F4",
          100: "#FFCFE5",
          200: "#FF9DCB",
          300: "#FF6BB1",
          400: "#FF3FA1",
          500: "#FF1493",
          600: "#D80F7C",
          700: "#A30C5E",
          800: "#700842",
          900: "#430527",
        },
        ink: {
          DEFAULT: "#1A0F2E",
          muted: "#5C4F75",
          subtle: "#8B7FA8",
        },
        surface: {
          DEFAULT: "#FFFFFF",
          alt: "#FBF7FE",
          elevated: "#FFFFFF",
        },
        border: {
          DEFAULT: "#EBDDF5",
          strong: "#D7B8EE",
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
          "linear-gradient(135deg, #FFE9F4 0%, #F6F0FB 50%, #EDE0F7 100%)",
        "gradient-subtle":
          "linear-gradient(180deg, #FFFFFF 0%, #FBF7FE 100%)",
      },
      boxShadow: {
        "brand": "0 16px 40px -12px rgba(123, 44, 191, 0.35)",
        "brand-soft": "0 8px 24px -8px rgba(255, 20, 147, 0.18)",
        "card": "0 1px 3px rgba(26,15,46,0.06), 0 8px 24px -12px rgba(123,44,191,0.10)",
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
        "shimmer": {
          "0%": { backgroundPosition: "-200% 0" },
          "100%": { backgroundPosition: "200% 0" },
        },
        "pulse-soft": {
          "0%, 100%": { opacity: "1" },
          "50%": { opacity: "0.5" },
        },
      },
      animation: {
        "fade-in": "fade-in 0.3s ease-out",
        "shimmer": "shimmer 2s linear infinite",
        "pulse-soft": "pulse-soft 2.5s cubic-bezier(0.4,0,0.6,1) infinite",
      },
    },
  },
  plugins: [require("tailwindcss-animate")],
};

export default config;
