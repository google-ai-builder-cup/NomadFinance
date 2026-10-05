import { ArrowRight, Cloud, Globe2, Lock, Sparkles } from "lucide-react";
import type { ReactNode } from "react";
import { Link } from "react-router-dom";

import RiskBadge from "@/components/common/RiskBadge";
import { Button } from "@/components/ui/button";
import AnimatedBackground from "@/components/visual/AnimatedBackground";
import CorridorGlobe from "@/components/visual/CorridorGlobe";
import ScoreRing from "@/components/visual/ScoreRing";
import { useI18n } from "@/hooks/useI18n";
import { cn } from "@/lib/utils";

function TrustChip({ icon, children }: { icon: ReactNode; children: ReactNode }) {
  return (
    <li className="inline-flex items-center gap-2 rounded-full border bg-card/80 px-3.5 py-2 text-[13px] font-semibold shadow-sm backdrop-blur">
      <span className="text-primary" aria-hidden="true">
        {icon}
      </span>
      {children}
    </li>
  );
}

/** A small floating glass card, always labelled "Example" so nobody reads it as live data. */
function ExampleCard({
  className,
  delay,
  label,
  children,
}: {
  className?: string;
  delay: string;
  label: string;
  children: ReactNode;
}) {
  const { t } = useI18n();
  return (
    <div
      style={{ animationDelay: delay }}
      className={cn(
        "glass absolute w-[44%] max-w-[13rem] animate-float rounded-2xl border p-3 shadow-lg sm:w-[34%]",
        className
      )}
    >
      <p className="text-[10.5px] font-extrabold uppercase tracking-widest text-subtle">
        {t("landing.example.label")} · {label}
      </p>
      {children}
    </div>
  );
}

export default function LandingHero() {
  const { t } = useI18n();

  return (
    <section id="top" className="relative overflow-hidden bg-hero-wash">
      <AnimatedBackground variant="mesh" />
      <div className="relative mx-auto grid w-full max-w-7xl items-center gap-4 px-4 pb-12 pt-4 md:px-8 lg:grid-cols-[1.02fr_.98fr] lg:gap-14 lg:pb-20 lg:pt-14">
        <div className="flex flex-col items-start gap-5">
          <p className="inline-flex items-center gap-2 rounded-full border bg-card/80 px-3.5 py-1.5 text-[13px] font-semibold shadow-sm backdrop-blur">
            <Sparkles className="h-4 w-4 text-gold-ink" aria-hidden="true" />
            {t("landing.hero.eyebrow")}
          </p>
          <h1 className="text-balance text-[clamp(2rem,5.4vw,4.25rem)] font-extrabold leading-[1.04] tracking-tight">
            {t("landing.hero.titleLead")}{" "}
            <span className="relative whitespace-nowrap text-primary">
              {t("landing.hero.titleAccent")}
              <svg
                viewBox="0 0 200 12"
                preserveAspectRatio="none"
                className="absolute inset-x-0 -bottom-1.5 h-2.5 w-full"
                aria-hidden="true"
              >
                <path
                  d="M2 8C40 2 80 2 120 6S180 8 198 3"
                  fill="none"
                  stroke="hsl(var(--brand-gold))"
                  strokeWidth="4"
                  strokeLinecap="round"
                />
              </svg>
            </span>
          </h1>
          <p className="max-w-[56ch] text-base text-muted-foreground md:text-lg">
            {t("landing.hero.subtitle")}
          </p>
          <div className="flex w-full flex-col gap-3 sm:w-auto sm:flex-row">
            <Button
              asChild
              size="lg"
              className="h-14 rounded-2xl bg-[hsl(var(--brand-gold))] px-8 text-base font-extrabold text-[hsl(var(--navy))] shadow-md hover:bg-[hsl(var(--brand-gold))]/90"
            >
              <Link to="/sign-in">
                {t("landing.hero.cta")}
                <ArrowRight className="ml-2 h-5 w-5" aria-hidden="true" />
              </Link>
            </Button>
            <Button
              asChild
              size="lg"
              variant="outline"
              className="h-14 rounded-2xl bg-card/80 px-8 text-base font-bold backdrop-blur"
            >
              <a href="#how">{t("landing.hero.secondaryCta")}</a>
            </Button>
          </div>
          <ul className="flex flex-wrap gap-2.5 pt-1" aria-label={t("landing.hero.trustLabel")}>
            <TrustChip icon={<Sparkles className="h-4 w-4" />}>
              {t("landing.hero.chips.gemini")}
            </TrustChip>
            <TrustChip icon={<Cloud className="h-4 w-4" />}>
              {t("landing.hero.chips.cloud")}
            </TrustChip>
            <TrustChip icon={<Globe2 className="h-4 w-4" />}>
              {t("landing.hero.chips.languages")}
            </TrustChip>
            <TrustChip icon={<Lock className="h-4 w-4" />}>
              {t("landing.hero.chips.data")}
            </TrustChip>
          </ul>
        </div>

        {/* On a phone the globe sits above the text, small enough to keep the call to action in
            view; from lg it is the right-hand centrepiece. */}
        <div className="order-first mx-auto w-full max-w-[13rem] sm:max-w-[24rem] lg:order-none lg:max-w-[36rem]">
          <div className="relative">
            <CorridorGlobe />
            <ExampleCard
              delay="0s"
              label={t("landing.example.compare")}
              className="-left-[3%] top-[6%] hidden sm:block"
            >
              <div className="mt-2 grid gap-1.5 text-xs font-semibold">
                <div className="flex items-center justify-between gap-2">
                  <span>{t("landing.example.providerA")}</span>
                  <span className="text-gold-ink">{t("landing.example.bestValue")}</span>
                </div>
                <div className="flex h-1.5 overflow-hidden rounded bg-muted">
                  <span className="w-[12%] bg-primary" />
                  <span className="w-[8%] bg-gold" />
                </div>
                <div className="flex items-center justify-between gap-2 text-muted-foreground">
                  <span>{t("landing.example.providerB")}</span>
                  <span>{t("landing.example.higherCost")}</span>
                </div>
                <div className="flex h-1.5 overflow-hidden rounded bg-muted">
                  <span className="w-[26%] bg-primary" />
                  <span className="w-[24%] bg-gold" />
                </div>
              </div>
            </ExampleCard>
            <ExampleCard
              delay="-2s"
              label={t("landing.example.contract")}
              className="-right-[3%] top-[34%] hidden sm:block"
            >
              <div className="mt-2">
                <RiskBadge level="caution">{t("contract.result.counts.caution")}</RiskBadge>
              </div>
              <p className="mt-2 text-xs font-semibold">{t("landing.example.clauses")}</p>
            </ExampleCard>
            <ExampleCard
              delay="-4s"
              label={t("landing.example.identity")}
              className="bottom-[2%] left-[6%] hidden items-center gap-3 sm:flex"
            >
              <div className="mt-2 flex items-center gap-3">
                <ScoreRing
                  value={72}
                  size={52}
                  strokeWidth={9}
                  color="hsl(var(--identity))"
                  label={t("landing.example.identityScoreLabel")}
                />
                <p className="text-xs font-bold">{t("landing.example.building")}</p>
              </div>
            </ExampleCard>
          </div>
        </div>
      </div>
    </section>
  );
}
