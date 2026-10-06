import { Check, TriangleAlert } from "lucide-react";

import SectionHeading from "@/components/landing/SectionHeading";
import RiskBadge from "@/components/common/RiskBadge";
import PriyaAvatar from "@/components/landing/PriyaAvatar";
import PriyaScene from "@/components/landing/PriyaScene";
import Reveal from "@/components/visual/Reveal";
import { useI18n } from "@/hooks/useI18n";
import { cn } from "@/lib/utils";

const BEFORE = ["b1", "b2", "b3"] as const;
const AFTER = ["a1", "a2", "a3"] as const;

export default function PriyaStory() {
  const { t } = useI18n();
  return (
    <section aria-labelledby="story-heading" className="py-16 md:py-24">
      <div className="mx-auto w-full max-w-7xl px-4 md:px-8">
        <div className="mb-10 grid items-center gap-10 lg:grid-cols-[minmax(0,1.1fr)_minmax(0,1fr)] lg:gap-14">
          <SectionHeading
            id="story-heading"
            kicker={t("landing.story.kicker")}
            title={t("landing.story.heading")}
            lead={t("landing.story.body")}
            className="mb-0 max-w-none"
            leadClassName="max-w-none text-justify [hyphens:auto]"
          />
          <Reveal delay={120}>
            <PriyaScene />
          </Reveal>
        </div>
        <div className="grid gap-5 md:grid-cols-2">
          {[
            {
              calm: false,
              items: BEFORE,
              list: "before",
              Icon: TriangleAlert,
              tint: "from-caution-tint",
              ink: "text-caution-ink",
            },
            {
              calm: true,
              items: AFTER,
              list: "after",
              Icon: Check,
              tint: "from-safe-tint",
              ink: "text-safe-ink",
            },
          ].map(({ calm, items, list, Icon, tint, ink }, i) => (
            <Reveal key={list} delay={i * 100}>
              <article
                className={cn(
                  "card-surface flex h-full flex-col gap-5 bg-gradient-to-br via-card to-card p-7",
                  tint,
                  calm && "card-edge"
                )}
              >
                <div className="flex items-center gap-4">
                  <PriyaAvatar calm={calm} label={t("landing.story.avatar")} />
                  <div className="grid gap-1.5">
                    <RiskBadge level={calm ? "safe" : "caution"} className="justify-self-start">
                      {t(`landing.story.${list}.badge`)}
                    </RiskBadge>
                    <h3 className="text-2xl font-extrabold tracking-tight">
                      {t(`landing.story.${list}.title`)}
                    </h3>
                  </div>
                </div>
                <ul className="grid gap-3 text-[15px] font-medium">
                  {items.map((key) => (
                    <li key={key} className="flex items-start gap-3">
                      <Icon className={cn("mt-0.5 h-4 w-4 shrink-0", ink)} aria-hidden="true" />
                      {t(`landing.story.${list}.${key}`)}
                    </li>
                  ))}
                </ul>
              </article>
            </Reveal>
          ))}
        </div>
      </div>
    </section>
  );
}
