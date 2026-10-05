import { cn } from "@/lib/utils";

/** A host → home pair as two overlapping country-code discs ("SG" over "PH"). Neutral monograms,
 * never flags or brand marks. Decorative: the text next to it names the corridor. */
export default function CountryPair({
  host,
  home,
  size = "md",
  className,
}: {
  host: string;
  home: string;
  size?: "sm" | "md";
  className?: string;
}) {
  const disc = size === "sm" ? "h-6 w-6 text-[9px]" : "h-7 w-7 text-[10px]";
  return (
    <span className={cn("inline-flex shrink-0", className)} aria-hidden="true">
      <span
        className={cn(
          "grid place-items-center rounded-full border-2 border-card bg-primary font-extrabold text-primary-foreground",
          disc
        )}
      >
        {host}
      </span>
      <span
        className={cn(
          "-ml-2 grid place-items-center rounded-full border-2 border-card bg-gold-ink font-extrabold text-white",
          disc
        )}
      >
        {home}
      </span>
    </span>
  );
}
