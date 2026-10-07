import { ArrowRight, Check } from "lucide-react";
import { Link } from "react-router-dom";

import SectionHeading from "@/components/landing/SectionHeading";
import PillarIllustration from "@/components/visual/PillarIllustration";
import Reveal from "@/components/visual/Reveal";
import TiltCard from "@/components/visual/TiltCard";
import { ALL_PILLAR_ITEMS, type PillarItem } from "@/components/layout/navItems";
import { useI18n } from "@/hooks/useI18n";
import { cn } from "@/lib/utils";
import { PILLAR_STYLES } from "@/utils/pillars";

const BULLETS = ["b1", "b2", "b3"] as const;

function PillarCard({ item }: { item: PillarItem }) {
  const { t } = useI18n();
  const { icon: Icon, to, nameKey, descriptionKey, pillar } = item;
  const style = PILLAR_STYLES[pillar];
  return (
    // Signed out, every pillar leads to sign-in; SignIn reads `from` to send the visitor on to
    // the page they actually wanted once they are authenticated.
    <Link
      to="/sign-in"
      state={{ from: { pathname: to } }}
      className={cn(
        "card-surface card-edge group flex h-full flex-col gap-5 overflow-hidden p-6 transition-shadow duration-base hover:shadow-lg md:p-7",
        style.band
      )}
    >
      <TiltCard className="mx-auto w-full max-w-[17rem] shrink-0">
        <PillarIllustration pillar={pillar} />
      </TiltCard>
      <div className="flex flex-1 flex-col gap-3">
        <h3 className="flex items-center gap-3 text-2xl font-extrabold tracking-tight">
          <span
            className={cn(
              "flex h-10 w-10 shrink-0 items-center justify-center rounded-xl shadow-sm",
              style.tile
            )}
          >
            <Icon className="h-5 w-5" aria-hidden="true" />
          </span>
          {t(nameKey)}
        </h3>
        <p className="text-[15px] text-muted-foreground">{t(descriptionKey)}</p>
        <ul className="grid gap-2 text-sm font-medium">
          {BULLETS.map((b) => (
            <li key={b} className="flex items-start gap-2.5">
              <Check className={cn("mt-0.5 h-4 w-4 shrink-0", style.text)} aria-hidden="true" />
              {t(`landing.pillars.items.${pillar}.${b}`)}
            </li>
          ))}
        </ul>
        <span
          className={cn(
            "mt-auto inline-flex items-center gap-1.5 pt-2 text-sm font-bold",
            style.text
          )}
        >
          {t("landing.pillars.cta")}
          <ArrowRight
            className="h-4 w-4 transition-transform group-hover:translate-x-0.5"
            aria-hidden="true"
          />
        </span>
      </div>
    </Link>
  );
}

/** Six equal cards in a 3 x 2 grid on a wide screen; a swipeable row on a phone. */
export default function PillarsSection() {
  const { t } = useI18n();
  return (
    <section id="pillars" aria-labelledby="pillars-heading" className="py-16 md:py-24">
      <div className="mx-auto w-full max-w-7xl px-4 md:px-8">
        <SectionHeading
          id="pillars-heading"
          kicker={t("landing.pillars.kicker")}
          title={t("landing.pillars.heading")}
        />
        <ul
          className={cn(
            "-mx-4 flex snap-x snap-mandatory gap-4 overflow-x-auto px-4 pb-3 md:-mx-8 md:px-8",
            "lg:mx-0 lg:grid lg:grid-cols-3 lg:gap-6 lg:overflow-visible lg:px-0 lg:pb-0"
          )}
        >
          {ALL_PILLAR_ITEMS.map((item, i) => (
            <li
              key={item.to}
              className="w-[86%] max-w-[26rem] shrink-0 snap-center sm:w-[70%] lg:w-auto lg:max-w-none lg:shrink"
            >
              <Reveal delay={i * 80} className="h-full">
                <PillarCard item={item} />
              </Reveal>
            </li>
          ))}
        </ul>
      </div>
    </section>
  );
}
