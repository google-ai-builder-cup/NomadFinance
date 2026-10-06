import { cn } from "@/lib/utils";

/** An illustrated avatar, not a photo: the same person before and after, with a worried or a
 * calm face. Skin and hair are illustration colours, not theme tokens. */
export default function PriyaAvatar({
  calm,
  label,
  className,
  size,
}: {
  calm: boolean;
  /** Omit when the avatar is purely decorative. */
  label?: string;
  className?: string;
  /** Pixel size for use nested inside another svg, where CSS sizing does not apply. */
  size?: number;
}) {
  return (
    <svg
      viewBox="0 0 120 120"
      role={label ? "img" : undefined}
      aria-label={label}
      aria-hidden={label ? undefined : true}
      width={size}
      height={size}
      className={cn(!size && "h-24 w-24", "shrink-0", className)}
    >
      <circle
        cx="60"
        cy="60"
        r="58"
        fill={calm ? "hsl(var(--safe-tint))" : "hsl(var(--caution-tint))"}
      />
      <path d="M20 112c4-22 20-34 40-34s36 12 40 34z" fill="hsl(var(--primary))" />
      <path
        d="M42 84c8 10 28 10 36 0l6 10c-10 12-38 12-48 0z"
        fill="hsl(var(--brand-gold))"
        opacity=".9"
      />
      <rect x="52" y="66" width="16" height="16" rx="6" fill="hsl(var(--skin))" />
      <ellipse cx="60" cy="48" rx="21" ry="24" fill="hsl(var(--skin-light))" />
      <path
        d="M38 46c-2-20 14-30 26-28 14 2 22 14 18 30-4-8-10-14-22-14-10 0-18 4-22 12z"
        fill="hsl(var(--hair))"
      />
      <circle cx="52" cy="50" r="2.2" fill="hsl(var(--hair))" />
      <circle cx="68" cy="50" r="2.2" fill="hsl(var(--hair))" />
      {calm ? (
        <path
          d="M52 60c4 5 12 5 16 0"
          fill="none"
          stroke="hsl(var(--mouth))"
          strokeWidth="2.4"
          strokeLinecap="round"
        />
      ) : (
        <>
          <path
            d="M53 62c4-3 10-3 14 0"
            fill="none"
            stroke="hsl(var(--mouth))"
            strokeWidth="2.4"
            strokeLinecap="round"
          />
          <path
            d="M48 43l8-2M72 41l8 2"
            stroke="hsl(var(--hair))"
            strokeWidth="2"
            strokeLinecap="round"
          />
        </>
      )}
    </svg>
  );
}
