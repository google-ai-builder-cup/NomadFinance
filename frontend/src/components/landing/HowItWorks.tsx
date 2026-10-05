import { useEffect, useRef, useState } from "react";

import SectionHeading from "@/components/landing/SectionHeading";
import RiskBadge from "@/components/common/RiskBadge";
import { Badge } from "@/components/ui/badge";
import PillarIllustration from "@/components/visual/PillarIllustration";
import { useI18n } from "@/hooks/useI18n";
import { cn } from "@/lib/utils";

const STEPS = ["upload", "read", "law", "report", "letter"] as const;

/** Index of the step nearest the middle of the screen, so the list can light it up as the worker
 * scrolls. Without IntersectionObserver the first step stays active and nothing is hidden. */
function useActiveStep(count: number) {
  const refs = useRef<(HTMLLIElement | null)[]>([]);
  const [active, setActive] = useState(0);

  useEffect(() => {
    if (typeof IntersectionObserver === "undefined") {
      return undefined;
    }
    const observer = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          if (entry.isIntersecting) {
            setActive(refs.current.indexOf(entry.target as HTMLLIElement));
          }
        }
      },
      { rootMargin: "-40% 0px -40% 0px" }
    );
    refs.current.slice(0, count).forEach((el) => el && observer.observe(el));
    return () => observer.disconnect();
  }, [count]);

  return { refs, active };
}

/** The Contract Shield pipeline as a scroll story: the document stays pinned on a wide screen
 * while the five steps scroll past and light up. On a phone it is a plain stacked list. */
export default function HowItWorks() {
  const { t } = useI18n();
  const { refs, active } = useActiveStep(STEPS.length);

  return (
    <section id="how" aria-labelledby="how-heading" className="bg-alt py-16 md:py-24">
      <div className="mx-auto w-full max-w-7xl px-4 md:px-8">
        <SectionHeading
          id="how-heading"
          kicker={t("landing.how.kicker")}
          title={t("landing.how.heading")}
        />
        <div className="grid items-start gap-8 lg:grid-cols-[.9fr_1.1fr] lg:gap-16">
          <div className="card-surface card-edge bg-gradient-to-br from-contract-tint via-card to-card p-6 md:p-9 lg:sticky lg:top-24">
            <div className="mx-auto max-w-[27rem]">
              <PillarIllustration pillar="contract" />
            </div>
            <div className="mt-2 flex flex-wrap justify-center gap-2">
              <Badge tone="info">{t("landing.how.scanning")}</Badge>
              <RiskBadge level="caution">{t("landing.how.flagged")}</RiskBadge>
            </div>
          </div>
          <ol className="grid gap-3.5">
            {STEPS.map((step, i) => (
              <li
                key={step}
                ref={(el) => {
                  refs.current[i] = el;
                }}
                aria-current={active === i ? "step" : undefined}
                className={cn(
                  "card-surface flex gap-4 p-5 transition-all duration-base",
                  active === i
                    ? "shadow-md ring-1 ring-contract/40 lg:scale-[1.015]"
                    : "lg:opacity-80"
                )}
              >
                <span
                  className={cn(
                    "grid h-10 w-10 shrink-0 place-items-center rounded-xl font-extrabold transition-colors duration-base",
                    active === i ? "bg-contract text-white" : "bg-contract-tint text-contract-ink"
                  )}
                >
                  {i + 1}
                </span>
                <div>
                  <h3 className="text-lg font-bold">{t(`landing.how.steps.${step}.title`)}</h3>
                  <p className="text-[15px] text-muted-foreground">
                    {t(`landing.how.steps.${step}.body`)}
                  </p>
                </div>
              </li>
            ))}
          </ol>
        </div>
      </div>
    </section>
  );
}
