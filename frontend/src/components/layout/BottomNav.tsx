import { NavLink } from "react-router-dom";

import { NAV_ITEMS, PILLAR_ITEMS } from "@/components/layout/navItems";
import { useI18n } from "@/hooks/useI18n";
import { cn } from "@/lib/utils";
import { PILLAR_STYLES } from "@/utils/pillars";

/** Phone navigation, reachable with a thumb: a floating rounded bar whose active tab is a pill in
 * its pillar's colour. Desktop and tablet use Sidebar instead. */
export default function BottomNav() {
  const { t } = useI18n();

  return (
    <nav
      aria-label={t("nav.primary")}
      className="pointer-events-none fixed inset-x-0 bottom-0 z-40 px-3 pb-[max(0.75rem,env(safe-area-inset-bottom))] md:hidden"
    >
      <ul className="glass pointer-events-auto grid grid-cols-5 gap-1 rounded-3xl border p-1.5 shadow-lg">
        {NAV_ITEMS.map(({ to, icon: Icon, labelKey }) => {
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
                <Icon className="h-5 w-5" aria-hidden="true" />
                <span className="max-w-full truncate">{t(labelKey)}</span>
              </NavLink>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}
