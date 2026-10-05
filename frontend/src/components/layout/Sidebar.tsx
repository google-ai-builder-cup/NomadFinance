import { Sparkles } from "lucide-react";
import { NavLink } from "react-router-dom";

import { NAV_ITEMS, PILLAR_ITEMS } from "@/components/layout/navItems";
import { useI18n } from "@/hooks/useI18n";
import { cn } from "@/lib/utils";
import { PILLAR_STYLES } from "@/utils/pillars";

/** Desktop and tablet navigation: icons only on a tablet, full labels from lg. The active item
 * wears its pillar's colour. Phones use BottomNav instead. */
export default function Sidebar() {
  const { t } = useI18n();

  return (
    <aside className="hidden shrink-0 border-r bg-card md:block md:w-[4.75rem] lg:w-64">
      <div className="sticky top-[calc(4rem+env(safe-area-inset-top))] flex h-[calc(100dvh-4rem)] flex-col gap-1 p-3">
        <nav aria-label={t("nav.primary")} className="flex flex-col gap-1">
          <p className="hidden px-3 pb-1 pt-2 text-[11px] font-bold uppercase tracking-widest text-subtle lg:block">
            {t("layout.sidebarHeading")}
          </p>
          {NAV_ITEMS.map(({ to, icon: Icon, labelKey }) => {
            const pillar = PILLAR_ITEMS.find((item) => item.to === to);
            const style = pillar ? PILLAR_STYLES[pillar.pillar] : null;
            return (
              <NavLink
                key={to}
                to={to}
                title={t(labelKey)}
                className={({ isActive }) =>
                  cn(
                    "group flex min-h-11 items-center gap-3 rounded-xl border-l-[3px] border-transparent px-3 text-sm font-semibold transition-colors md:justify-center lg:justify-start",
                    isActive
                      ? cn(style?.tint ?? "bg-accent", style?.text ?? "text-primary", style?.border)
                      : "text-muted-foreground hover:bg-accent hover:text-foreground"
                  )
                }
              >
                {({ isActive }) => (
                  <>
                    <span
                      className={cn(
                        "flex h-8 w-8 shrink-0 items-center justify-center rounded-lg transition-colors",
                        isActive
                          ? (style?.tile ?? "bg-primary text-primary-foreground")
                          : "bg-muted"
                      )}
                    >
                      <Icon className="h-4 w-4" aria-hidden="true" />
                    </span>
                    <span className="md:sr-only lg:not-sr-only">{t(labelKey)}</span>
                  </>
                )}
              </NavLink>
            );
          })}
        </nav>
        <div className="mt-auto hidden rounded-2xl border bg-alt p-4 lg:block">
          <p className="flex items-center gap-2 text-sm font-bold">
            <Sparkles className="h-4 w-4 text-primary" aria-hidden="true" />
            {t("layout.protected.title")}
          </p>
          <p className="mt-1 text-xs text-muted-foreground">{t("layout.protected.body")}</p>
        </div>
      </div>
    </aside>
  );
}
