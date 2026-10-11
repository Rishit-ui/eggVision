import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        primary: {
          DEFAULT: "#16a34a",
          foreground: "#ffffff",
          hover: "#15803d",
        },
        fresh: {
          DEFAULT: "#22c55e",
          foreground: "#ffffff",
        },
        okay: {
          DEFAULT: "#f59e0b",
          foreground: "#ffffff",
        },
        old: {
          DEFAULT: "#ef4444",
          foreground: "#ffffff",
        },
        background: "#ffffff",
        foreground: "#09090b",
        muted: {
          DEFAULT: "#f4f4f5",
          foreground: "#71717a",
        },
        border: "#e4e4e7",
        destructive: {
          DEFAULT: "#ef4444",
          foreground: "#fafafa",
        },
      },
    },
  },
  plugins: [],
};
export default config;
