import type { Config } from "tailwindcss";
import tailwindcssAnimate from "tailwindcss-animate";

// A risk state or pillar has the same five shades everywhere, so they are built once here.
const risk = (name: string) => ({
  DEFAULT: `hsl(var(--${name}))`,
  ink: `hsl(var(--${name}-ink))`,
  tint: `hsl(var(--${name}-tint))`,
  "tint-ink": `hsl(var(--${name}-tint-ink))`,
});
const pillar = (name: string) => ({
  DEFAULT: `hsl(var(--${name}))`,
  soft: `hsl(var(--${name}-soft))`,
  deep: `hsl(var(--${name}-deep))`,
  tint: `hsl(var(--${name}-tint))`,
  ink: `hsl(var(--${name}-ink))`,
});

export default {
  darkMode: ["class"],
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    container: {
      center: true,
      padding: "1rem",
      screens: {
        "2xl": "1280px",
      },
    },
    extend: {
      fontFamily: {
        // Latin first, then the two Indic scripts the app ships in, so Hindi, Nepali and
        // Bengali never fall back to a system face with broken conjuncts.
        sans: [
          '"Plus Jakarta Sans"',
          '"Noto Sans Devanagari"',
          '"Noto Sans Bengali"',
          "system-ui",
          "-apple-system",
          '"Segoe UI"',
          "Roboto",
          "sans-serif",
        ],
      },
      colors: {
        border: "hsl(var(--border))",
        input: "hsl(var(--input))",
        ring: "hsl(var(--ring))",
        background: "hsl(var(--background))",
        foreground: "hsl(var(--foreground))",
        primary: {
          DEFAULT: "hsl(var(--primary))",
          foreground: "hsl(var(--primary-foreground))",
        },
        secondary: {
          DEFAULT: "hsl(var(--secondary))",
          foreground: "hsl(var(--secondary-foreground))",
        },
        destructive: {
          DEFAULT: "hsl(var(--destructive))",
          foreground: "hsl(var(--destructive-foreground))",
        },
        muted: {
          DEFAULT: "hsl(var(--muted))",
          foreground: "hsl(var(--muted-foreground))",
        },
        subtle: "hsl(var(--subtle-foreground))",
        accent: {
          DEFAULT: "hsl(var(--accent))",
          foreground: "hsl(var(--accent-foreground))",
        },
        popover: {
          DEFAULT: "hsl(var(--popover))",
          foreground: "hsl(var(--popover-foreground))",
        },
        card: {
          DEFAULT: "hsl(var(--card))",
          foreground: "hsl(var(--card-foreground))",
        },
        // Gold is the sparing accent: the primary call to action, key numbers, the logo dot.
        gold: {
          DEFAULT: "hsl(var(--brand-gold))",
          ink: "hsl(var(--gold-ink))",
        },
        paper: {
          DEFAULT: "hsl(var(--paper))",
          ink: "hsl(var(--paper-ink))",
          muted: "hsl(var(--paper-muted))",
        },
        navy: "hsl(var(--navy))",
        aqua: "hsl(var(--aqua))",
        deep: "hsl(var(--deep))",
        alt: "hsl(var(--alt))",
        safe: risk("safe"),
        caution: risk("caution"),
        danger: risk("danger"),
        info: risk("info"),
        remit: pillar("remit"),
        contract: pillar("contract"),
        radar: pillar("radar"),
        identity: pillar("identity"),
        scam: pillar("scam"),
        coach: pillar("coach"),
        sdg: {
          1: "hsl(var(--sdg-1))",
          8: "hsl(var(--sdg-8))",
          10: "hsl(var(--sdg-10))",
          16: "hsl(var(--sdg-16))",
        },
      },
      borderRadius: {
        // 12 / 16 / 24 px scale; the shadcn names stay so existing primitives follow it.
        sm: "calc(var(--radius) - 4px)",
        md: "calc(var(--radius) - 2px)",
        lg: "var(--radius)",
        xl: "1rem",
        "2xl": "1.5rem",
      },
      boxShadow: {
        sm: "var(--shadow-sm)",
        DEFAULT: "var(--shadow-sm)",
        md: "var(--shadow-md)",
        lg: "var(--shadow-lg)",
        glow: "var(--shadow-glow)",
      },
      backgroundImage: {
        "hero-wash": "var(--gradient-hero)",
        "band-wash": "var(--gradient-band)",
      },
      transitionTimingFunction: {
        "out-soft": "var(--ease-out)",
        "in-out-soft": "var(--ease-in-out)",
      },
      transitionDuration: {
        fast: "var(--dur-fast)",
        base: "var(--dur-base)",
        slow: "var(--dur-slow)",
      },
      keyframes: {
        // Ambient and explanatory motion only. globals.css switches all of it off under
        // prefers-reduced-motion, and nothing here flashes or loops faster than ~2 s.
        float: {
          "0%, 100%": { transform: "translateY(0)" },
          "50%": { transform: "translateY(-7px)" },
        },
        drift: {
          "0%, 100%": { transform: "translate3d(0,0,0) scale(1)" },
          "50%": { transform: "translate3d(50px,34px,0) scale(1.12)" },
        },
        "drift-reverse": {
          "0%, 100%": { transform: "translate3d(0,0,0) scale(1.08)" },
          "50%": { transform: "translate3d(-60px,-26px,0) scale(0.95)" },
        },
        "fade-up": {
          from: { opacity: "0", transform: "translateY(14px)" },
          to: { opacity: "1", transform: "translateY(0)" },
        },
        "pop-in": {
          from: { opacity: "0", transform: "scale(0.6)" },
          to: { opacity: "1", transform: "scale(1)" },
        },
        shimmer: {
          to: { backgroundPosition: "-200% 0" },
        },
        "dash-flow": {
          to: { strokeDashoffset: "-18" },
        },
        travel: {
          "0%": { offsetDistance: "0%", opacity: "0" },
          "12%": { opacity: "1" },
          "88%": { opacity: "1" },
          "100%": { offsetDistance: "100%", opacity: "0" },
        },
        ping: {
          "0%": { transform: "scale(0.6)", opacity: "0.55" },
          "100%": { transform: "scale(2.2)", opacity: "0" },
        },
        scan: {
          "0%, 100%": { transform: "translateY(0)" },
          "50%": { transform: "translateY(-82px)" },
        },
        sweep: {
          to: { transform: "rotate(360deg)" },
        },
        blip: {
          "0%, 100%": { opacity: "0.15" },
          "30%": { opacity: "1" },
        },
        grow: {
          from: { transform: "scaleY(0.2)" },
          to: { transform: "scaleY(1)" },
        },
        cycle: {
          "0%": { opacity: "0", transform: "translateY(10px)" },
          "3%, 14%": { opacity: "1", transform: "none" },
          "17%, 100%": { opacity: "0", transform: "translateY(-10px)" },
        },
        "step-on": {
          "0%, 2%": { backgroundColor: "hsl(var(--muted))", color: "hsl(var(--muted-foreground))" },
          "8%, 16%": {
            backgroundColor: "hsl(var(--primary))",
            color: "hsl(var(--primary-foreground))",
          },
          "22%, 100%": {
            backgroundColor: "hsl(var(--muted))",
            color: "hsl(var(--muted-foreground))",
          },
        },
        "live-pulse": {
          "70%": { boxShadow: "0 0 0 10px rgb(16 185 129 / 0)" },
          "100%": { boxShadow: "0 0 0 0 rgb(16 185 129 / 0)" },
        },
      },
      animation: {
        float: "float 4.8s ease-in-out infinite",
        "float-slow": "float 6.5s ease-in-out infinite",
        drift: "drift 24s ease-in-out infinite",
        "drift-reverse": "drift-reverse 28s ease-in-out infinite",
        "fade-up": "fade-up var(--dur-slow) var(--ease-out) both",
        "pop-in": "pop-in var(--dur-slow) var(--ease-out) both",
        shimmer: "shimmer 1.6s linear infinite",
        "dash-flow": "dash-flow 1.4s linear infinite",
        ping: "ping 2.6s ease-out infinite",
        travel: "travel 4s linear infinite",
        scan: "scan 3.4s ease-in-out infinite",
        sweep: "sweep 4.5s linear infinite",
        blip: "blip 4s infinite",
        grow: "grow 2.4s var(--ease-out) infinite alternate",
        cycle: "cycle 12s infinite",
        "live-pulse": "live-pulse 2s infinite",
        "step-on": "step-on 8.4s infinite",
      },
    },
  },
  plugins: [tailwindcssAnimate],
} satisfies Config;
