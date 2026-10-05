import { Check, TriangleAlert } from "lucide-react";

import SectionHeading from "@/components/landing/SectionHeading";
import RiskBadge from "@/components/common/RiskBadge";
import Reveal from "@/components/visual/Reveal";
import { useI18n } from "@/hooks/useI18n";
import { cn } from "@/lib/utils";

/** An illustrated avatar, not a photo: the same person before and after, with a worried or a
 * calm face. Skin and hair are illustration colours, not theme tokens. */
function Avatar({ calm, label }: { calm: boolean; label: string }) {
  return (
    <svg viewBox="0 0 120 120" role="img" aria-label={label} className="h-24 w-24 shrink-0">
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

const BEFORE = ["b1", "b2", "b3"] as const;
const AFTER = ["a1", "a2", "a3"] as const;

export default function PriyaStory() {
  const { t } = useI18n();
  return (
    <section aria-labelledby="story-heading" className="py-16 md:py-24">
      <div className="mx-auto w-full max-w-7xl px-4 md:px-8">
        <SectionHeading
          id="story-heading"
          kicker={t("landing.story.kicker")}
          title={t("landing.story.heading")}
          lead={t("landing.story.body")}
        />
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
                  <Avatar calm={calm} label={t("landing.story.avatar")} />
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
