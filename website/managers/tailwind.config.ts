import type { Config } from "tailwindcss";


export default {
  content: ["./index.html", "./src/**/*.{vue,ts,tsx}"],
  theme: {
    extend: {
      colors: {
        brand: {
          ink: "#14213d",
          sea: "#1e3a5f",
          mint: "#4cb286",
          sand: "#f3e9d2",
          amber: "#f4a259",
        },
      },
      boxShadow: {
        panel: "0 18px 45px rgba(15, 23, 42, 0.12)",
      },
      fontFamily: {
        sans: ["IBM Plex Sans", "Noto Sans SC", "PingFang SC", "sans-serif"],
        mono: ["JetBrains Mono", "Consolas", "monospace"],
      },
    },
  },
  plugins: [],
} satisfies Config;
