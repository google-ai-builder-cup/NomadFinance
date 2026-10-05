import { useEffect, useState } from "react";

const prefersReducedMotion = () =>
  typeof window !== "undefined" &&
  window.matchMedia?.("(prefers-reduced-motion: reduce)").matches === true;

/** Counts from 0 to `target` once `active` turns true. Reduced motion, or a target that cannot
 * be animated, shows the final value straight away. Eased out so it settles instead of stopping. */
export function useCountUp(target: number, active: boolean, durationMs = 1400): number {
  const still = prefersReducedMotion() || !Number.isFinite(target);
  const [value, setValue] = useState(0);

  useEffect(() => {
    if (still || !active) {
      return undefined;
    }
    const start = performance.now();
    let frame = 0;
    const tick = (now: number) => {
      const t = Math.min(1, (now - start) / durationMs);
      setValue(target * (1 - Math.pow(1 - t, 3)));
      if (t < 1) {
        frame = requestAnimationFrame(tick);
      }
    };
    frame = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frame);
  }, [target, active, durationMs, still]);

  return still ? target : value;
}
