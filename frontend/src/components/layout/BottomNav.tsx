import { NavLink, useLocation } from "react-router-dom";

import { PILLAR_ITEMS, visibleNavItems } from "@/components/layout/navItems";
import { useFeatureFlags } from "@/hooks/useFeatureFlag";
import { useI18n } from "@/hooks/useI18n";
import { cn } from "@/lib/utils";
import { PILLAR_STYLES } from "@/utils/pillars";

// Five tabs fit with their labels (v1.0). From six up, a label no longer fits in a column that
// narrow ("Remitt…"), so only the active tab shows its label, in a wider column, and the rest
// are icons; every label stays in the page for screen readers.
const COMPACT_FROM = 6;
const ACTIVE_WIDTH = "1.7fr";

/** Phone navigation, reachable with a thumb: a floating rounded bar whose active tab is a pill in
 * its pillar's colour. Desktop and tablet use Sidebar instead. */
export default function BottomNav() {
  const { t } = useI18n();
  const { flags } = useFeatureFlags();
  const { pathname } = useLocation();
  const items = visibleNavItems(flags);
  const compact = items.length >= COMPACT_FROM;
  const activeIndex = items.findIndex(({ to }) => pathname === to || pathname.startsWith(`${to}/`));

  return (
    <nav
      aria-label={t("nav.primary")}
      className="pointer-events-none fixed inset-x-0 bottom-0 z-40 px-3 pb-[max(0.75rem,env(safe-area-inset-bottom))] md:hidden"
    >
      <ul
        className={cn(
          "glass pointer-events-auto grid gap-1 rounded-3xl border p-1.5 shadow-lg",
          !compact && "grid-cols-5"
        )}
        style={
          compact
            ? {
                gridTemplateColumns: items
                  .map((_, index) => (index === activeIndex ? ACTIVE_WIDTH : "1fr"))
                  .join(" "),
              }
            : undefined
        }
      >
        {items.map(({ to, icon: Icon, labelKey }) => {
          const pillar = PILLAR_ITEMS.find((item) => item.to === to);
          const style = pillar ? PILLAR_STYLES[pillar.pillar] : null;
          return (
            <li key={to}>
              <NavLink
                to={to}
                className={({ isActive }) =>
                  cn(
                    "flex min-h-14 flex-col items-center justify-center gap-0.5 rounded-2xl px-1 text-[11px] font-semibold leading-tight transition-colors duration-base",
                    isActive
                      ? cn(style?.tint ?? "bg-accent", style?.text ?? "text-primary")
                      : "text-muted-foreground"
                  )
                }
              >
                {({ isActive }) => (
                  <>
                    <Icon className="h-5 w-5" aria-hidden="true" />
                    <span className={compact && !isActive ? "sr-only" : "max-w-full truncate"}>
                      {t(labelKey)}
                    </span>
                  </>
                )}
              </NavLink>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}
