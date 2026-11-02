import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: {
          950: "#0b0c0f",
          900: "#111318",
          850: "#16181e",
          800: "#1c1f27",
          700: "#262a34",
        },
        mist: "#9aa1ad",
        line: "rgba(255,255,255,0.08)",
        accent: {
          DEFAULT: "#5eead4",
          dim: "#134e4a",
        },
      },
      boxShadow: {
        card: "0 1px 0 rgba(255,255,255,0.04), 0 8px 24px rgba(0,0,0,0.24)",
      },
    },
  },
  plugins: [],
};

export default config;
