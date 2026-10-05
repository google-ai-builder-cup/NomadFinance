import { Lock } from "lucide-react";
import type { ReactNode } from "react";

import SectionHeading from "@/components/landing/SectionHeading";
import { Badge } from "@/components/ui/badge";
import Reveal from "@/components/visual/Reveal";
import { useI18n } from "@/hooks/useI18n";
import { cn } from "@/lib/utils";
import { SUPPORTED_LANGUAGES } from "@/lib/languages";
import { CORRIDOR_IDS } from "@/types/enums";
import { FX_REFRESH_HOURS, MEASURED_METRICS, PROTECTED_WORDS } from "@/utils/landingMetrics";

const PIPELINE_STEPS = [
  "extract",
  "detect",
  "law",
  "translate",
  "compare",
  "score",
  "letter",
] as const;
const TIERS = [
  { key: "extraction", bar: "bg-remit" },
  { key: "reasoning", bar: "bg-contract" },
  { key: "translation", bar: "bg-gold" },
  { key: "embeddings", bar: "bg-radar" },
] as const;

function Cell({
  className,
  delay,
  dashed = false,
  children,
}: {
  className: string;
  delay: number;
  dashed?: boolean;
  children: ReactNode;
}) {
  return (
    <Reveal delay={delay} className={className}>
      <article
        className={cn(
          "card-surface flex h-full flex-col gap-3.5 p-6",
          dashed ? "border-dashed shadow-none" : "card-edge"
        )}
      >
        {children}
      </article>
    </Reveal>
  );
}

const bigNumber = "text-[3.25rem] font-extrabold leading-none tracking-tight";

function CorridorChip({ id }: { id: string }) {
  const [from, to] = id.split("-");
  return (
    <li className="inline-flex items-center gap-2 rounded-full border bg-muted py-1.5 pl-1.5 pr-3 text-[13px] font-bold">
      <span className="inline-flex">
        <span className="grid h-7 w-7 place-items-center rounded-full border-2 border-card bg-primary text-[10px] font-extrabold text-primary-foreground">
          {from}
        </span>
        <span className="-ml-2 grid h-7 w-7 place-items-center rounded-full border-2 border-card bg-gold-ink text-[10px] font-extrabold text-white">
          {to}
        </span>
      </span>
      {from} → {to}
    </li>
  );
}

export default function PerformanceBento() {
  const { t } = useI18n();
  const seconds = MEASURED_METRICS.contractAnalysisSeconds;

  return (
    <section
      id="performance"
      aria-labelledby="performance-heading"
      className="relative overflow-hidden bg-band-wash py-16 md:py-24"
    >
      <div className="mx-auto w-full max-w-7xl px-4 md:px-8">
        <SectionHeading
          id="performance-heading"
          kicker={t("landing.performance.kicker")}
          title={t("landing.performance.heading")}
          lead={t("landing.performance.lead")}
        />
        <div className="grid gap-4 md:grid-cols-6 lg:grid-cols-12">
          <Cell className="md:col-span-6 lg:col-span-5" delay={0}>
            <p className={bigNumber}>{CORRIDOR_IDS.length}</p>
            <h3 className="text-lg font-bold">{t("landing.performance.corridors.title")}</h3>
            <ul className="flex flex-wrap gap-2">
              {CORRIDOR_IDS.map((id) => (
                <CorridorChip key={id} id={id} />
              ))}
            </ul>
            <p className="mt-auto text-sm text-muted-foreground">
              {t("landing.performance.corridors.body")}
            </p>
          </Cell>

          <Cell className="md:col-span-3 lg:col-span-4" delay={80}>
            <p className={bigNumber}>{SUPPORTED_LANGUAGES.length}</p>
            <h3 className="text-lg font-bold">{t("landing.performance.languages.title")}</h3>
            <p className="sr-only">
              {t("landing.performance.languages.sr", { words: PROTECTED_WORDS.join(", ") })}
            </p>
            <div
              aria-hidden="true"
              className="relative my-1 h-[1.25em] text-[clamp(1.75rem,3vw,2.5rem)] font-extrabold tracking-tight text-primary"
            >
              {PROTECTED_WORDS.map((word, i) => (
                <span
                  key={word}
                  style={{ animationDelay: `${i * 2}s` }}
                  className={cn(
                    "absolute left-0 top-0 animate-cycle whitespace-nowrap",
                    i === 0 ? "opacity-100" : "opacity-0"
                  )}
                >
                  {word}
                </span>
              ))}
            </div>
            <ul className="mt-auto flex flex-wrap gap-1.5" aria-hidden="true">
              {SUPPORTED_LANGUAGES.map(({ code, nativeName }) => (
                <li key={code}>
                  <Badge>{nativeName}</Badge>
                </li>
              ))}
            </ul>
          </Cell>

          <Cell className="md:col-span-3 lg:col-span-3" delay={160}>
            <div className="flex items-center gap-2.5">
              <span
                className="h-2.5 w-2.5 animate-live-pulse rounded-full bg-safe"
                aria-hidden="true"
              />
              <span className="text-[10.5px] font-extrabold uppercase tracking-widest text-safe-ink">
                {t("landing.performance.fx.live")}
              </span>
            </div>
            <p className="text-5xl font-extrabold leading-none tracking-tight">
              {FX_REFRESH_HOURS}
              <span className="ml-1 text-xl text-muted-foreground">
                {t("landing.performance.fx.unit")}
              </span>
            </p>
            <h3 className="text-base font-bold">
              {t("landing.performance.fx.title", { hours: FX_REFRESH_HOURS })}
            </h3>
            <svg
              viewBox="0 0 200 56"
              className="mt-auto h-14 w-full text-primary"
              aria-hidden="true"
            >
              <path
                d="M0 40C20 36 28 18 48 24S78 44 98 30S130 8 150 20S182 30 200 12V56H0Z"
                fill="currentColor"
                opacity=".12"
              />
              <path
                d="M0 40C20 36 28 18 48 24S78 44 98 30S130 8 150 20S182 30 200 12"
                fill="none"
                stroke="currentColor"
                strokeWidth="2.4"
                strokeLinecap="round"
              />
              <circle cx="200" cy="12" r="4" fill="hsl(var(--brand-gold))" />
            </svg>
          </Cell>

          <Cell className="md:col-span-6 lg:col-span-7" delay={0}>
            <div className="flex flex-wrap items-center justify-between gap-2">
              <h3 className="text-lg font-bold">{t("landing.performance.pipeline.title")}</h3>
              <Badge tone="info">
                {t("landing.performance.pipeline.count", { count: PIPELINE_STEPS.length })}
              </Badge>
            </div>
            <ol className="grid gap-x-5 gap-y-2.5 sm:grid-cols-2">
              {PIPELINE_STEPS.map((step, i) => (
                <li key={step} className="flex items-center gap-2.5 text-sm font-semibold">
                  <span
                    style={{ animationDelay: `${i * 1.2 - 0.2}s` }}
                    className="grid h-6 w-6 shrink-0 animate-step-on place-items-center rounded-full bg-muted text-xs font-extrabold text-muted-foreground"
                  >
                    {i + 1}
                  </span>
                  {t(`landing.performance.pipeline.steps.${step}`)}
                </li>
              ))}
            </ol>
            <p className="text-sm text-muted-foreground">
              {t("landing.performance.pipeline.body")}
            </p>
          </Cell>

          <Cell className="md:col-span-6 lg:col-span-5" delay={80}>
            <h3 className="text-lg font-bold">
              {t("landing.performance.tiers.title", { count: TIERS.length })}
            </h3>
            <ul className="grid gap-2.5">
              {TIERS.map(({ key, bar }) => (
                <li key={key} className="flex items-center gap-3 rounded-xl bg-muted p-2.5">
                  <span className={cn("h-9 w-2.5 shrink-0 rounded", bar)} aria-hidden="true" />
                  <div>
                    <p className="text-sm font-bold">
                      {t(`landing.performance.tiers.${key}.name`)}
                    </p>
                    <p className="text-[13px] text-muted-foreground">
                      {t(`landing.performance.tiers.${key}.body`)}
                    </p>
                  </div>
                </li>
              ))}
            </ul>
          </Cell>

          <Cell className="md:col-span-3 lg:col-span-4" delay={0}>
            <h3 className="text-lg font-bold">{t("landing.performance.data.title")}</h3>
            <ul className="grid gap-2.5 text-sm">
              {(["worldBank", "ilo"] as const).map((key) => (
                <li key={key} className="rounded-xl bg-muted p-3">
                  <p className="font-bold">{t(`landing.performance.data.${key}.name`)}</p>
                  <p className="text-[13px] text-muted-foreground">
                    {t(`landing.performance.data.${key}.body`)}
                  </p>
                </li>
              ))}
            </ul>
          </Cell>

          <Cell className="md:col-span-3 lg:col-span-4" delay={80} dashed={seconds === null}>
            {seconds === null ? (
              <>
                <p className="text-[10.5px] font-extrabold uppercase tracking-widest text-subtle">
                  {t("landing.performance.time.pending")}
                </p>
                <p className="text-5xl font-extrabold leading-none tracking-tight text-subtle">—</p>
              </>
            ) : (
              <p className="text-5xl font-extrabold leading-none tracking-tight">
                {seconds}
                <span className="ml-1 text-xl text-muted-foreground">
                  {t("landing.performance.time.unit")}
                </span>
              </p>
            )}
            <h3 className="text-base font-bold">{t("landing.performance.time.title")}</h3>
            {seconds === null && (
              <p className="mt-auto text-[13px] text-muted-foreground">
                {t("landing.performance.time.note")}
              </p>
            )}
          </Cell>

          <Cell className="md:col-span-6 lg:col-span-4" delay={160}>
            <Lock className="h-5 w-5 text-primary" aria-hidden="true" />
            <h3 className="text-lg font-bold">{t("landing.performance.privacy.title")}</h3>
            <p className="text-sm text-muted-foreground">{t("landing.performance.privacy.body")}</p>
          </Cell>
        </div>
      </div>
    </section>
  );
}
