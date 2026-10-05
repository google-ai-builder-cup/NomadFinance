import { useId } from "react";

export interface BrandMarkProps {
  size?: number;
  className?: string;
}

/** The N-mark: a rounded teal square, a white N and the gold dot. Decorative; the wordmark next
 * to it carries the name. */
export default function BrandMark({ size = 34, className }: BrandMarkProps) {
  const id = useId();
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 34 34"
      aria-hidden="true"
      focusable="false"
      className={className}
    >
      <defs>
        <linearGradient id={id} x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor="hsl(var(--logo-from))" />
          <stop offset="1" stopColor="hsl(var(--logo-to))" />
        </linearGradient>
      </defs>
      <rect width="34" height="34" rx="10" fill={`url(#${id})`} />
      <rect
        x=".5"
        y=".5"
        width="33"
        height="33"
        rx="9.5"
        fill="none"
        stroke="white"
        strokeOpacity=".28"
      />
      <path
        d="M10 24V11.5l14 12.5V15"
        fill="none"
        stroke="white"
        strokeWidth="3.2"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <circle cx="24" cy="9.2" r="3" fill="hsl(var(--brand-gold))" />
    </svg>
  );
}
