import { Link } from "react-router-dom";

import BrandMark from "@/components/visual/BrandMark";
import { useI18n } from "@/hooks/useI18n";

const LINKS = [
  { href: "#pillars", key: "landing.header.pillars" },
  { href: "#how", key: "landing.header.how" },
  { href: "#impact", key: "landing.header.impact" },
] as const;

const linkClass =
  "inline-flex min-h-11 items-center rounded-lg px-1 text-sm font-medium hover:text-foreground";

/** Landing footer: brand, a short disclaimer, anchors and the sources of the industry figures. */
export default function LandingFooter() {
  const { t } = useI18n();
  return (
    <footer className="border-t bg-alt py-10 text-muted-foreground">
      <div className="mx-auto flex w-full max-w-7xl flex-wrap justify-between gap-8 px-4 md:px-8">
        <div className="flex max-w-sm flex-col gap-3">
          <p className="flex items-center gap-2.5 text-lg font-extrabold text-foreground">
            <BrandMark size={30} />
            {t("landing.brand")}
          </p>
          <p className="text-sm">{t("layout.footer.tagline")}</p>
          <p className="text-sm">{t("layout.footer.disclaimer")}</p>
        </div>
        <nav aria-label={t("landing.footer.links")} className="flex flex-wrap items-start gap-x-6">
          {LINKS.map(({ href, key }) => (
            <a key={href} href={href} className={linkClass}>
              {t(key)}
            </a>
          ))}
          <Link to="/sign-in" className={linkClass}>
            {t("landing.header.signIn")}
          </Link>
        </nav>
      </div>
      <div className="mx-auto mt-6 flex w-full max-w-7xl flex-wrap justify-between gap-3 border-t px-4 pt-5 text-xs md:px-8">
        <span>{t("landing.footer.event")}</span>
        <span>{t("landing.footer.sources")}</span>
        <span>{t("layout.footer.rights", { year: new Date().getFullYear() })}</span>
      </div>
    </footer>
  );
}
