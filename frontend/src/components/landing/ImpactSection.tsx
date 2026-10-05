import SectionHeading from "@/components/landing/SectionHeading";
import Reveal from "@/components/visual/Reveal";
import { useI18n } from "@/hooks/useI18n";

const GOALS = [
  { key: "g8", number: 8, tile: "bg-sdg-8" },
  { key: "g10", number: 10, tile: "bg-sdg-10" },
  { key: "g16", number: 16, tile: "bg-sdg-16" },
] as const;

/** The three UN goals the product supports. Official colours appear only on the small number
 * tile; the claim is alignment with a goal, never a measured result. */
export default function ImpactSection() {
  const { t } = useI18n();
  return (
    <section id="impact" aria-labelledby="impact-heading" className="py-16 md:py-24">
      <div className="mx-auto w-full max-w-7xl px-4 md:px-8">
        <SectionHeading
          id="impact-heading"
          kicker={t("landing.impact.kicker")}
          title={t("landing.impact.heading")}
        />
        <ul className="grid gap-5 md:grid-cols-3">
          {GOALS.map(({ key, number, tile }, i) => (
            <li key={key}>
              <Reveal delay={i * 80} className="h-full">
                <article className="card-surface flex h-full flex-col gap-3.5 p-6">
                  <div className="flex items-center gap-3.5">
                    <span
                      className={`grid h-[3.25rem] w-[3.25rem] shrink-0 place-items-center rounded-2xl text-[1.375rem] font-extrabold text-white ${tile}`}
                      aria-hidden="true"
                    >
                      {number}
                    </span>
                    <h3 className="text-lg font-extrabold leading-tight">
                      <span className="sr-only">{t("landing.impact.goal", { number })} </span>
                      {t(`landing.impact.${key}.title`)}
                    </h3>
                  </div>
                  <p className="text-[15px] text-muted-foreground">
                    {t(`landing.impact.${key}.body`)}
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
