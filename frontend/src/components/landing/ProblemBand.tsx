import SectionHeading from "@/components/landing/SectionHeading";
import CountUp from "@/components/visual/CountUp";
import Reveal from "@/components/visual/Reveal";
import { useI18n } from "@/hooks/useI18n";
import {
  COST_TARGET_PCT,
  GLOBAL_AVERAGE_COST_FLOOR_PCT,
  INDUSTRY_FACTS,
  type IndustryFact,
} from "@/utils/landingMetrics";

type FactKey = keyof typeof INDUSTRY_FACTS;

const ORDER: readonly FactKey[] = ["migrants", "remittances", "lostToFees", "target"];

function KpiCard({ factKey, delay }: { factKey: FactKey; delay: number }) {
  const { t } = useI18n();
  const fact: IndustryFact = INDUSTRY_FACTS[factKey];
  return (
    <Reveal delay={delay}>
      <article className="card-surface card-edge flex h-full min-h-[14rem] flex-col gap-3.5 p-6">
        <p className="text-[clamp(2.75rem,5vw,4rem)] font-extrabold leading-none tracking-tight">
          <CountUp value={fact.value} prefix={fact.prefix} />
          <span className="text-gold-ink">{fact.suffix}</span>
        </p>
        <h3 className="text-base font-semibold leading-snug">
          {t(`landing.problem.${factKey}.label`)}
        </h3>
        {factKey === "target" && (
          <div className="grid gap-1.5 text-xs font-bold" aria-hidden="true">
            <div className="flex items-center gap-2">
              <span className="w-12">{t("landing.problem.target.goal")}</span>
              <span className="h-2 rounded bg-safe" style={{ width: `${COST_TARGET_PCT * 10}%` }} />
              {COST_TARGET_PCT}%
            </div>
            <div className="flex items-center gap-2">
              <span className="w-12">{t("landing.problem.target.today")}</span>
              <span
                className="h-2 rounded bg-danger"
                style={{ width: `${GLOBAL_AVERAGE_COST_FLOOR_PCT * 10}%` }}
              />
              {GLOBAL_AVERAGE_COST_FLOOR_PCT}%+
            </div>
          </div>
        )}
        <p className="mt-auto border-t border-dashed pt-2.5 text-xs text-subtle">
          {t("landing.problem.source", { name: fact.source })}
        </p>
      </article>
    </Reveal>
  );
}

export default function ProblemBand() {
  const { t } = useI18n();
  return (
    <section id="problem" aria-labelledby="problem-heading" className="py-16 md:py-24">
      <div className="mx-auto w-full max-w-7xl px-4 md:px-8">
        <SectionHeading
          id="problem-heading"
          kicker={t("landing.problem.kicker")}
          title={t("landing.problem.heading")}
          lead={t("landing.problem.lead")}
        />
        <ul className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {ORDER.map((key, i) => (
            <li key={key}>
              <KpiCard factKey={key} delay={i * 80} />
            </li>
          ))}
        </ul>
      </div>
    </section>
  );
}
