import { Menu, X } from "lucide-react";
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import LanguageSelector from "@/components/layout/LanguageSelector";
import ThemeToggle from "@/components/layout/ThemeToggle";
import { Button } from "@/components/ui/button";
import BrandMark from "@/components/visual/BrandMark";
import { useI18n } from "@/hooks/useI18n";

const SECTIONS = [
  { id: "problem", key: "landing.header.problem" },
  { id: "performance", key: "landing.header.performance" },
  { id: "pillars", key: "landing.header.pillars" },
  { id: "how", key: "landing.header.how" },
  { id: "impact", key: "landing.header.impact" },
] as const;

/** Sticky glass header: logo, section anchors on a wide screen, language, theme and sign-in.
 * Below lg the anchors collapse into a panel behind a menu button. */
export default function LandingHeader() {
  const { t } = useI18n();
  const [open, setOpen] = useState(false);

  useEffect(() => {
    if (!open) {
      return undefined;
    }
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        setOpen(false);
      }
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [open]);

  return (
    <header className="glass sticky top-0 z-40 border-b pt-[env(safe-area-inset-top)]">
      <div className="mx-auto flex h-16 w-full max-w-7xl items-center gap-3 px-4 md:px-8">
        <a
          href="#top"
          className="flex shrink-0 items-center gap-2.5 rounded-lg text-lg font-extrabold tracking-tight"
        >
          <BrandMark size={34} />
          {/* The mark alone below 340 px: with the wordmark the three buttons no longer fit. */}
          <span className="max-[339px]:sr-only">{t("landing.brand")}</span>
        </a>
        <nav aria-label={t("landing.header.sections")} className="ml-4 hidden gap-1 xl:flex">
          {SECTIONS.map(({ id, key }) => (
            <a
              key={id}
              href={`#${id}`}
              className="whitespace-nowrap rounded-lg px-3 py-2.5 text-sm font-semibold text-muted-foreground transition-colors hover:bg-accent hover:text-foreground"
            >
              {t(key)}
            </a>
          ))}
        </nav>
        <div className="ml-auto flex items-center gap-2">
          <LanguageSelector />
          <ThemeToggle />
          <Button asChild className="hidden h-11 rounded-xl px-5 font-bold sm:inline-flex">
            <Link to="/sign-in">{t("landing.header.signIn")}</Link>
          </Button>
          <button
            type="button"
            aria-expanded={open}
            aria-controls="landing-menu"
            aria-label={open ? t("landing.header.closeMenu") : t("landing.header.openMenu")}
            onClick={() => setOpen((v) => !v)}
            className="flex h-11 w-11 items-center justify-center rounded-xl border bg-card shadow-sm xl:hidden"
          >
            {open ? (
              <X className="h-5 w-5" aria-hidden="true" />
            ) : (
              <Menu className="h-5 w-5" aria-hidden="true" />
            )}
          </button>
        </div>
      </div>
      {open && (
        <nav
          id="landing-menu"
          aria-label={t("landing.header.sections")}
          className="animate-fade-up border-t bg-card px-4 pb-4 pt-2 xl:hidden"
        >
          <ul className="mx-auto flex max-w-7xl flex-col">
            {SECTIONS.map(({ id, key }) => (
              <li key={id}>
                <a
                  href={`#${id}`}
                  onClick={() => setOpen(false)}
                  className="flex min-h-12 items-center rounded-lg px-3 text-base font-semibold hover:bg-accent"
                >
                  {t(key)}
                </a>
              </li>
            ))}
            <li className="pt-2 sm:hidden">
              <Button asChild className="h-12 w-full rounded-xl font-bold">
                <Link to="/sign-in">{t("landing.header.signIn")}</Link>
              </Button>
            </li>
          </ul>
        </nav>
      )}
    </header>
  );
}
