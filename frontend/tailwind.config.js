/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{vue,js,ts,jsx,tsx}"],
  darkMode: "class",
  theme: {
    extend: {
      colors: {
        // 西大蓝（主色）
        swu: {
          DEFAULT: "#003D7A",
          50: "#E3F2FD",
          100: "#BBDEFB",
          200: "#90CAF9",
          300: "#64B5F6",
          400: "#1565C0",
          500: "#003D7A",
          600: "#003366",
          700: "#002855",
          800: "#001A3D",
          900: "#000F26",
        },
        // 西大红
        crimson: {
          DEFAULT: "#B22222",
          50: "#FFEBEE",
          400: "#DC143C",
          500: "#B22222",
          600: "#8B0000",
        },
        // 校徽金
        gold: {
          DEFAULT: "#D4AF37",
          light: "#F5DEB3",
        },
      },
      fontFamily: {
        sans: [
          "PingFang SC",
          "Hiragino Sans GB",
          "Microsoft YaHei",
          "Source Han Sans",
          "-apple-system",
          "BlinkMacSystemFont",
          "Helvetica Neue",
          "Arial",
          "sans-serif",
        ],
        serif: [
          "Source Han Serif",
          "STZhongsong",
          "SimSun",
          "serif",
        ],
      },
      boxShadow: {
        card: "0 1px 3px rgba(0,0,0,0.04), 0 1px 2px rgba(0,0,0,0.06)",
        "card-hover": "0 4px 14px rgba(0,61,122,0.12)",
        glow: "0 0 0 4px rgba(0,61,122,0.12)",
      },
      animation: {
        "fade-in": "fade-in 0.4s ease-out",
        "slide-up": "slide-up 0.4s cubic-bezier(0.16, 1, 0.3, 1)",
      },
      keyframes: {
        "fade-in": {
          "0%": { opacity: "0" },
          "100%": { opacity: "1" },
        },
        "slide-up": {
          "0%": { opacity: "0", transform: "translateY(12px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
      },
    },
  },
  plugins: [],
};
