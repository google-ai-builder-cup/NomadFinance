import { Cloud, Lock, Sparkles } from "lucide-react";
import type { ReactNode } from "react";
import { Link } from "react-router-dom";

import AnimatedBackground from "@/components/visual/AnimatedBackground";
import BrandMark from "@/components/visual/BrandMark";
import { CorridorGlobePoster } from "@/components/visual/CorridorGlobe";
import { useI18n } from "@/hooks/useI18n";

/** The split screen shared by sign-in and onboarding: the brand on one side, the form on the
 * other. Below lg the brand collapses into a slim banner above the form. */
export default function AuthSplit({ children }: { children: ReactNode }) {
  const { t } = useI18n();

  return (
    <div className="grid min-h-screen min-h-dvh grid-cols-[minmax(0,1fr)] lg:grid-cols-[1.05fr_1fr]">
      <aside className="relative hidden flex-col justify-between gap-8 overflow-hidden bg-hero-wash p-10 lg:flex xl:p-14">
        <AnimatedBackground variant="mesh" />
        <Link
          to="/"
          className="relative flex items-center gap-2.5 text-xl font-extrabold tracking-tight"
        >
          <BrandMark size={38} />
          {t("landing.brand")}
        </Link>
        <div className="relative mx-auto w-full max-w-[26rem]">
          <CorridorGlobePoster />
        </div>
        <div className="relative space-y-4">
          <h2 className="max-w-[18ch] text-balance text-4xl font-extrabold leading-[1.1] tracking-tight">
            {t("landing.hero.titleLead")}
          </h2>
          <p className="max-w-[44ch] text-muted-foreground">{t("landing.hero.subtitle")}</p>
          <ul className="flex flex-wrap gap-2">
            {[
              { icon: Sparkles, label: t("landing.hero.chips.gemini") },
              { icon: Cloud, label: t("landing.hero.chips.cloud") },
              { icon: Lock, label: t("landing.hero.chips.data") },
            ].map(({ icon: Icon, label }) => (
              <li
                key={label}
                className="inline-flex items-center gap-2 rounded-full border bg-card/80 px-3.5 py-2 text-[13px] font-semibold shadow-sm backdrop-blur"
              >
                <Icon className="h-4 w-4 text-primary" aria-hidden="true" />
                {label}
              </li>
            ))}
          </ul>
        </div>
      </aside>

      <div className="flex flex-col bg-background">
        <Link
          to="/"
          className="flex items-center gap-2.5 bg-hero-wash px-4 py-4 text-lg font-extrabold tracking-tight lg:hidden"
        >
          <BrandMark size={32} />
          {t("landing.brand")}
        </Link>
        <main
          id="main-content"
          tabIndex={-1}
          className="flex flex-1 flex-col justify-center px-4 py-8 focus:outline-none md:px-10"
        >
          <div className="mx-auto flex w-full max-w-sm flex-col gap-6 md:max-w-md">{children}</div>
        </main>
      </div>
    </div>
  );
}
