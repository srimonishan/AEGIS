/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  darkMode: "media",
  theme: {
    extend: {
      colors: {
        aegis: {
          bg: "#0b0f14",
          panel: "#121821",
          border: "#1f2937",
          accent: "#3b82f6",
          danger: "#ef4444",
          warn: "#f59e0b",
          safe: "#22c55e",
        },
      },
    },
  },
  plugins: [],
};
