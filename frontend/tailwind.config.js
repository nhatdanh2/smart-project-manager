/** @type {import('tailwindcss').Config} */
module.exports = {
  darkMode: "class",
  content: [
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        primary: "#6366F1",
        danger: "#EF4444",
        warning: "#F59E0B",
        success: "#10B981",
        ghost: "#9CA3AF",
        border: "#E5E7EB",
        input: "#E5E7EB",
        ring: "#6366F1",
        accent: "#F3F4F6",
        "accent-foreground": "#0F172A",
        muted: "#9CA3AF",
        "muted-foreground": "#6B7280",
        background: "#FFFFFF",
        foreground: "#0F172A",
        card: "#FFFFFF",
        "card-foreground": "#0F172A",
      },
      fontFamily: {
        sans: ["Inter", "system-ui", "sans-serif"],
      },
      keyframes: {
        "accordion-down": {
          from: { height: "0" },
          to: { height: "var(--radix-accordion-content-height)" },
        },
        "accordion-up": {
          from: { height: "var(--radix-accordion-content-height)" },
          to: { height: "0" },
        },
      },
      animation: {
        "accordion-down": "accordion-down 0.2s ease-out",
        "accordion-up": "accordion-up 0.2s ease-out",
      },
    },
  },
  plugins: [require("tailwindcss-animate")],
};
