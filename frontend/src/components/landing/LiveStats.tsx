import SectionHeading from "@/components/landing/SectionHeading";
import CountUp from "@/components/visual/CountUp";
import Reveal from "@/components/visual/Reveal";
import { useI18n } from "@/hooks/useI18n";
import { usePublicStats } from "@/hooks/usePublicStats";
import { cn } from "@/lib/utils";
import type { PublicStats } from "@/types/publicStats";

interface LiveStat {
  key: string;
  field: keyof Omit<PublicStats, "generated_at">;
}

// The order is what a visitor most wants to know first: what it protects against, then how many
// people use it. Only the first MAX_CARDS that have a figure are shown.
const STATS: readonly LiveStat[] = [
  { key: "contracts", field: "contracts_checked" },
  { key: "scamChecked", field: "scam_messages_checked" },
  { key: "scamsFlagged", field: "scams_flagged" },
  { key: "reports", field: "radar_reports" },
  { key: "alerts", field: "alerts_generated" },
  { key: "workers", field: "workers" },
];

const MAX_CARDS = 6;
// Fewer than this reads as a half-empty row, so the strip stays out instead.
const MIN_CARDS = 3;

/** Platform totals read live from Firestore through the public stats endpoint. A total that is
 * missing or zero is left out rather than shown as "0", and the whole strip is left out while it
 * loads, if the call fails, or when too few totals exist yet to fill a row. */
export default function LiveStats() {
  const { t } = useI18n();
  const stats = usePublicStats();
  const shown = STATS.flatMap((stat) => {
    const value = stats.data?.[stat.field];
    return typeof value === "number" && value > 0 ? [{ ...stat, value }] : [];
  }).slice(0, MAX_CARDS);

  if (shown.length < MIN_CARDS) {
    return null;
  }
  return (
    <section id="live" aria-labelledby="live-heading" className="py-16 md:py-24">
      <div className="mx-auto w-full max-w-7xl px-4 md:px-8">
        <SectionHeading
          id="live-heading"
          kicker={t("landing.live.kicker")}
          title={t("landing.live.heading")}
          lead={t("landing.live.lead")}
        />
        <ul
          className={cn(
            "grid gap-4 sm:grid-cols-2",
            // Four cards in a row of four, not three and one on its own.
            shown.length === 4 ? "lg:grid-cols-4" : "lg:grid-cols-3"
          )}
        >
          {shown.map(({ key, value }, i) => (
            <li key={key}>
              <Reveal delay={i * 80} className="h-full">
                <article className="card-surface card-edge flex h-full min-h-[14rem] flex-col gap-3.5 p-6">
                  <p className="text-[clamp(2.75rem,5vw,4rem)] font-extrabold leading-none tracking-tight tabular-nums">
                    <CountUp value={value} />
                  </p>
                  <h3 className="text-base font-semibold leading-snug">
                    {t(`landing.live.items.${key}`)}
                  </h3>
                  <p className="mt-auto border-t border-dashed pt-2.5 text-xs text-subtle">
                    {t("landing.live.source")}
                  </p>
                </article>
              </Reveal>
            </li>
          ))}
        </ul>
      </div>
    </section>
  );
}
