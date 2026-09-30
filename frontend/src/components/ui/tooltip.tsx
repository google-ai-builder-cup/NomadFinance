import { Info } from "lucide-react";
import { useEffect, useId, useRef, useState, type ReactNode } from "react";

// A minimal, self-built disclosure, the same spirit as skeleton.tsx: not the shadcn/Radix
// Tooltip primitive (that needs @radix-ui/react-tooltip, not a dependency here), and click
// to toggle rather than hover, so it works the same on a touch phone as on desktop.
export interface InfoTooltipProps {
  /** Announced by the trigger button (`aria-label`); the visible content is `children`. */
  label: string;
  children: ReactNode;
}

export function InfoTooltip({ label, children }: InfoTooltipProps) {
  const [open, setOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);
  const contentId = useId();

  useEffect(() => {
    if (!open) {
      return;
    }
    function onPointerDown(event: MouseEvent) {
      if (!containerRef.current?.contains(event.target as Node)) {
        setOpen(false);
      }
    }
    function onKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") {
        setOpen(false);
      }
    }
    document.addEventListener("mousedown", onPointerDown);
    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("mousedown", onPointerDown);
      document.removeEventListener("keydown", onKeyDown);
    };
  }, [open]);

  return (
    <div ref={containerRef} className="relative inline-flex">
      <button
        type="button"
        aria-label={label}
        aria-expanded={open}
        aria-describedby={open ? contentId : undefined}
        onClick={() => setOpen((current) => !current)}
        className="inline-flex h-5 w-5 shrink-0 items-center justify-center rounded-full text-muted-foreground hover:text-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
      >
        <Info className="h-4 w-4" aria-hidden="true" />
      </button>
      {open && (
        <div
          id={contentId}
          role="tooltip"
          className="absolute left-1/2 top-full z-20 mt-2 w-64 -translate-x-1/2 text-left rounded-md border bg-popover p-3 text-xs leading-relaxed text-popover-foreground shadow-md"
        >
          {children}
        </div>
      )}
    </div>
  );
}
