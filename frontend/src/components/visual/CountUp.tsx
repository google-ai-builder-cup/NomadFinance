import { useCountUp } from "@/hooks/useCountUp";
import { useI18n } from "@/hooks/useI18n";
import { useReveal } from "@/hooks/useReveal";
import i18n from "@/lib/i18n";

export interface CountUpProps {
  value: number;
  /** Decimal places to show while and after counting. */
  decimals?: number;
  prefix?: string;
  suffix?: string;
  className?: string;
}

/** A figure that counts up when it scrolls into view. The real value is always in the markup for
 * screen readers; the counting text is hidden from them so they never hear it change. */
export default function CountUp({ value, decimals = 0, prefix, suffix, className }: CountUpProps) {
  useI18n(); // re-renders on a language switch so the digits follow it
  const [ref, shown] = useReveal<HTMLSpanElement>();
  const current = useCountUp(value, shown);
  const format = (n: number) =>
    n.toLocaleString(i18n.resolvedLanguage ?? "en", {
      minimumFractionDigits: decimals,
      maximumFractionDigits: decimals,
    });
  return (
    <span ref={ref} className={className}>
      <span className="sr-only">
        {prefix}
        {format(value)}
        {suffix}
      </span>
      <span aria-hidden="true">
        {prefix}
        {format(current)}
        {suffix}
      </span>
    </span>
  );
}
