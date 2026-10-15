import {
  Bell,
  Flag,
  GraduationCap,
  type LucideIcon,
  ScanSearch,
  ShieldAlert,
  ShieldCheck,
  Users,
} from "lucide-react";

import SectionHeading from "@/components/landing/SectionHeading";
import CountUp from "@/components/visual/CountUp";
import Reveal from "@/components/visual/Reveal";
import { useI18n } from "@/hooks/useI18n";
import { usePublicStats } from "@/hooks/usePublicStats";
import { cn } from "@/lib/utils";
import type { PublicStats } from "@/types/publicStats";
import { PILLAR_STYLES, type PillarKey } from "@/utils/pillars";

interface LiveStat {
  key: string;
  field: keyof Omit<PublicStats, "generated_at">;
  icon: LucideIcon;
  pillar: PillarKey;
}

// The order is what a visitor most wants to know first: what it protects against, then how many
// people use it. Only the first MAX_CARDS that have a figure are shown.
const STATS: readonly LiveStat[] = [
  { key: "contracts", field: "contracts_checked", icon: ShieldCheck, pillar: "contract" },
  { key: "scamChecked", field: "scam_messages_checked", icon: ScanSearch, pillar: "scam" },
  { key: "scamsFlagged", field: "scams_flagged", icon: ShieldAlert, pillar: "scam" },
  { key: "reports", field: "radar_reports", icon: Flag, pillar: "radar" },
  { key: "alerts", field: "alerts_generated", icon: Bell, pillar: "radar" },
  { key: "plans", field: "coach_plans", icon: GraduationCap, pillar: "coach" },
  { key: "workers", field: "workers", icon: Users, pillar: "remit" },
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
        <ul className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {shown.map(({ key, icon: Icon, pillar, value }, i) => (
            <li key={key}>
              <Reveal delay={i * 70} className="h-full">
                <article className="card-surface card-edge flex h-full items-center gap-4 p-5 sm:p-6">
                  <span
                    className={cn(
                      "grid h-12 w-12 shrink-0 place-items-center rounded-2xl",
                      PILLAR_STYLES[pillar].tile
                    )}
                    aria-hidden="true"
                  >
                    <Icon className="h-6 w-6" />
                  </span>
                  <div className="min-w-0">
                    <p className="text-[clamp(2rem,4vw,2.75rem)] font-extrabold leading-none tracking-tight tabular-nums">
                      <CountUp value={value} />
                    </p>
                    <h3 className="mt-1.5 text-sm font-semibold leading-snug text-muted-foreground">
                      {t(`landing.live.items.${key}`)}
                    </h3>
                  </div>
                </article>
              </Reveal>
            </li>
          ))}
        </ul>
      </div>
    </section>
  );
}
