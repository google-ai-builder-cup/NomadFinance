import { ArrowRight } from "lucide-react";
import { Link } from "react-router-dom";

import { Button } from "@/components/ui/button";
import AnimatedBackground from "@/components/visual/AnimatedBackground";
import { useI18n } from "@/hooks/useI18n";

/** The closing call to action, on the same mesh as the hero. */
export default function FinalCta() {
  const { t } = useI18n();
  return (
    <section aria-labelledby="final-cta-heading" className="relative overflow-hidden bg-hero-wash">
      <AnimatedBackground variant="mesh" />
      <div className="relative mx-auto flex w-full max-w-3xl flex-col items-center gap-4 px-4 py-16 text-center md:py-24">
        <h2
          id="final-cta-heading"
          className="text-balance text-[clamp(1.875rem,4.4vw,3.25rem)] font-extrabold leading-tight tracking-tight"
        >
          {t("landing.finalCta.heading")}
        </h2>
        <p className="text-lg text-muted-foreground">{t("landing.finalCta.subtitle")}</p>
        <Button
          asChild
          size="lg"
          className="mt-2 h-14 rounded-2xl bg-gold px-9 text-base font-extrabold text-navy shadow-md hover:bg-gold/90"
        >
          <Link to="/sign-in">
            {t("landing.finalCta.button")}
            <ArrowRight className="ml-2 h-5 w-5" aria-hidden="true" />
          </Link>
        </Button>
      </div>
    </section>
  );
}
