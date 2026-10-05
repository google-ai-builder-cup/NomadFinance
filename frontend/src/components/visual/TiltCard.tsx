import { useRef, type PointerEvent, type ReactNode } from "react";

import { cn } from "@/lib/utils";

const MAX_TILT = 7;

/** Tilts a few degrees towards the pointer over a mouse. Touch, pen and reduced motion get a
 * flat card: there is no hover to react to, and a tilt would only fight scrolling. */
export default function TiltCard({
  className,
  children,
}: {
  className?: string;
  children: ReactNode;
}) {
  const ref = useRef<HTMLDivElement>(null);

  function canTilt(): boolean {
    return (
      window.matchMedia("(hover: hover) and (pointer: fine)").matches &&
      !window.matchMedia("(prefers-reduced-motion: reduce)").matches
    );
  }

  function onMove(event: PointerEvent<HTMLDivElement>) {
    const el = ref.current;
    if (!el || event.pointerType !== "mouse" || !canTilt()) {
      return;
    }
    const rect = el.getBoundingClientRect();
    const px = (event.clientX - rect.left) / rect.width - 0.5;
    const py = (event.clientY - rect.top) / rect.height - 0.5;
    el.style.transform = `perspective(900px) rotateX(${(-py * MAX_TILT).toFixed(2)}deg) rotateY(${(px * MAX_TILT).toFixed(2)}deg)`;
  }

  function reset() {
    if (ref.current) {
      ref.current.style.transform = "";
    }
  }

  return (
    <div
      ref={ref}
      onPointerMove={onMove}
      onPointerLeave={reset}
      className={cn(
        "transition-transform duration-base ease-out-soft will-change-transform",
        className
      )}
    >
      {children}
    </div>
  );
}
