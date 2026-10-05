import { useEffect, useRef } from "react";

import { ARC_CORRIDORS, CITIES, LAND_DOTS, project, type CityCode } from "@/components/visual/geo";

const CENTER_LON = 108;
const CENTER_LAT = 14;
// The land outlines only cover Asia-Pacific, so the globe sways around it instead of spinning
// through empty ocean.
const SWAY_DEG = 16;
const SWAY_SECONDS = 22;
const RECEIVING: readonly CityCode[] = ["PH", "IN", "ID"];

interface Paint {
  hi: string;
  mid: string;
  lo: string;
  dot: string;
  aqua: string;
  gold: string;
  primary: string;
  label: string;
  card: string;
}

function readPaint(el: HTMLElement): Paint {
  const style = getComputedStyle(el);
  const hsl = (name: string) => `hsl(${style.getPropertyValue(name).trim()})`;
  return {
    hi: hsl("--globe-hi"),
    mid: hsl("--globe-mid"),
    lo: hsl("--globe-lo"),
    dot: hsl("--globe-dot"),
    aqua: hsl("--aqua"),
    gold: hsl("--brand-gold"),
    primary: hsl("--primary"),
    label: hsl("--globe-label"),
    card: hsl("--card"),
  };
}

function quadPoint(a: [number, number], c: [number, number], b: [number, number], t: number) {
  const u = 1 - t;
  return [
    u * u * a[0] + 2 * u * t * c[0] + t * t * b[0],
    u * u * a[1] + 2 * u * t * c[1] + t * t * b[1],
  ] as const;
}

/** The animated globe: a canvas 2D orthographic render of the same dots, arcs and cities as the
 * poster, swaying gently, with a coin travelling each corridor. It pauses while off-screen or
 * in a background tab. No pointer handlers, so it never traps a scroll gesture on a phone. */
export default function CorridorGlobeCanvas({ onReady }: { onReady: () => void }) {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    const ctx = canvas?.getContext("2d");
    if (!canvas || !ctx) {
      return undefined;
    }
    let paint = readPaint(canvas);
    let size = 0;
    let frame = 0;
    let visible = true;
    let startedAt = performance.now();
    let announced = false;

    const resize = () => {
      const rect = canvas.getBoundingClientRect();
      const dpr = Math.min(window.devicePixelRatio || 1, 2);
      size = rect.width;
      canvas.width = Math.round(rect.width * dpr);
      canvas.height = Math.round(rect.width * dpr);
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    };

    const draw = (now: number) => {
      const elapsed = (now - startedAt) / 1000;
      const lon0 = CENTER_LON + SWAY_DEG * Math.sin((elapsed / SWAY_SECONDS) * Math.PI * 2);
      const scale = size / 520;
      const cx = 260 * scale;
      const cy = 262 * scale;
      const R = 215 * scale;
      ctx.clearRect(0, 0, size, size);

      const halo = ctx.createRadialGradient(cx, cy, R * 0.96, cx, cy, R * 1.16);
      halo.addColorStop(0, "transparent");
      halo.addColorStop(0.5, paint.dot.replace(")", " / 0.16)"));
      halo.addColorStop(1, "transparent");
      ctx.fillStyle = halo;
      ctx.beginPath();
      ctx.arc(cx, cy, R * 1.16, 0, Math.PI * 2);
      ctx.fill();

      const sphere = ctx.createRadialGradient(
        cx - R * 0.32,
        cy - R * 0.44,
        R * 0.1,
        cx,
        cy,
        R * 1.05
      );
      sphere.addColorStop(0, paint.hi);
      sphere.addColorStop(0.5, paint.mid);
      sphere.addColorStop(1, paint.lo);
      ctx.fillStyle = sphere;
      ctx.beginPath();
      ctx.arc(cx, cy, R, 0, Math.PI * 2);
      ctx.fill();

      ctx.fillStyle = paint.dot.replace(")", " / 0.55)");
      const dotR = 1.5 * scale;
      for (const [lon, lat] of LAND_DOTS) {
        const p = project(lon, lat, lon0, CENTER_LAT);
        if (p.depth > 0.02) {
          ctx.beginPath();
          ctx.arc(cx + p.x * R, cy - p.y * R, dotR, 0, Math.PI * 2);
          ctx.fill();
        }
      }
      ctx.strokeStyle = paint.dot.replace(")", " / 0.25)");
      ctx.lineWidth = 1.2 * scale;
      ctx.beginPath();
      ctx.arc(cx, cy, R, 0, Math.PI * 2);
      ctx.stroke();

      const at = (code: CityCode): [number, number] => {
        const [lon, lat] = CITIES[code];
        const p = project(lon, lat, lon0, CENTER_LAT);
        return [cx + p.x * R, cy - p.y * R];
      };

      ARC_CORRIDORS.forEach(([from, to], i) => {
        const a = at(from);
        const b = at(to);
        const mx = (a[0] + b[0]) / 2;
        const my = (a[1] + b[1]) / 2;
        let dx = mx - cx;
        let dy = my - cy;
        const len = Math.hypot(dx, dy) || 1;
        dx /= len;
        dy /= len;
        const lift = (22 + (Math.hypot(a[0] - b[0], a[1] - b[1]) / scale) * 0.28) * scale;
        const control: [number, number] = [mx + dx * lift, my + dy * lift - 8 * scale];
        const grad = ctx.createLinearGradient(a[0], a[1], b[0], b[1]);
        grad.addColorStop(0, paint.primary);
        grad.addColorStop(1, paint.gold);
        ctx.strokeStyle = grad;
        ctx.lineWidth = 2 * scale;
        ctx.lineCap = "round";
        ctx.beginPath();
        ctx.moveTo(a[0], a[1]);
        ctx.quadraticCurveTo(control[0], control[1], b[0], b[1]);
        ctx.stroke();

        for (const offset of [0, 0.5]) {
          const t = (elapsed / (3.4 + (i % 3) * 0.7) + i * 0.27 + offset) % 1;
          const [x, y] = quadPoint(a, control, b, t);
          ctx.globalAlpha = Math.min(1, t * 8, (1 - t) * 8);
          ctx.fillStyle = offset ? paint.primary : paint.gold;
          ctx.beginPath();
          ctx.arc(x, y, (offset ? 2.4 : 3.4) * scale, 0, Math.PI * 2);
          ctx.fill();
          ctx.globalAlpha = 1;
        }
      });

      ctx.font = `800 ${11 * scale}px "Plus Jakarta Sans", system-ui, sans-serif`;
      (Object.keys(CITIES) as CityCode[]).forEach((code) => {
        const [lon, lat] = CITIES[code];
        const p = project(lon, lat, lon0, CENTER_LAT);
        if (p.depth <= 0.02) {
          return;
        }
        const [x, y] = at(code);
        const receiving = RECEIVING.includes(code);
        ctx.fillStyle = receiving ? paint.gold : paint.aqua;
        ctx.strokeStyle = paint.card;
        ctx.lineWidth = 1.5 * scale;
        ctx.beginPath();
        ctx.arc(x, y, 4 * scale, 0, Math.PI * 2);
        ctx.fill();
        ctx.stroke();
        ctx.lineWidth = 3 * scale;
        ctx.strokeText(code, x + (receiving ? 10 : -22) * scale, y + 15 * scale);
        ctx.fillStyle = paint.label;
        ctx.fillText(code, x + (receiving ? 10 : -22) * scale, y + 15 * scale);
      });

      if (!announced) {
        announced = true;
        onReady();
      }
    };

    const loop = (now: number) => {
      if (visible && !document.hidden) {
        draw(now);
      }
      frame = requestAnimationFrame(loop);
    };

    resize();
    frame = requestAnimationFrame(loop);
    const observer = new IntersectionObserver(([entry]) => {
      visible = entry.isIntersecting;
    });
    observer.observe(canvas);
    const resizeObserver = new ResizeObserver(resize);
    resizeObserver.observe(canvas);
    // The theme is a class on <html>: repaint with the new colours when it flips.
    const theme = new MutationObserver(() => {
      paint = readPaint(canvas);
    });
    theme.observe(document.documentElement, { attributes: true, attributeFilter: ["class"] });
    startedAt = performance.now();

    return () => {
      cancelAnimationFrame(frame);
      observer.disconnect();
      resizeObserver.disconnect();
      theme.disconnect();
    };
  }, [onReady]);

  return <canvas ref={canvasRef} aria-hidden="true" className="absolute inset-0 h-full w-full" />;
}
