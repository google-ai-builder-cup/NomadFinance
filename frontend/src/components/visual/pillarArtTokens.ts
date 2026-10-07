import type { FaceFills } from "@/components/visual/iso";
import { PILLAR_STYLES, pillarVar, type PillarKey } from "@/utils/pillars";

export interface Palette {
  base: string;
  soft: string;
  deep: string;
  faces: FaceFills;
  floor: FaceFills;
  paper: FaceFills;
  ink: string;
  glow: string;
}

export function palette(pillar: PillarKey): Palette {
  const s = PILLAR_STYLES[pillar];
  const base = pillarVar(s.base);
  const soft = pillarVar(s.soft);
  const deep = pillarVar(s.deep);
  return {
    base,
    soft,
    deep,
    faces: { top: soft, left: base, right: deep },
    floor: {
      top: "hsl(var(--muted))",
      left: "hsl(var(--border))",
      right: "hsl(var(--subtle-foreground) / .45)",
    },
    paper: { top: "hsl(var(--card))", left: "hsl(var(--card))", right: "hsl(var(--border))" },
    ink: "hsl(var(--subtle-foreground))",
    glow: pillarVar(s.soft, 0.5),
  };
}

export const GOLD = "hsl(var(--brand-gold))";
