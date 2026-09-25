import { NavLink } from "react-router-dom";

import { NAV_ITEMS } from "@/components/layout/navItems";
import { useI18n } from "@/hooks/useI18n";
import { cn } from "@/lib/utils";

/** Desktop and tablet navigation. Phones use BottomNav instead. */
export default function Sidebar() {
  const { t } = useI18n();

  return (
    <aside className="hidden w-56 shrink-0 border-r md:block">
      <nav
        aria-label={t("nav.primary")}
        className="sticky top-14 flex flex-col gap-1 p-3 md:h-[calc(100vh-3.5rem)]"
      >
        {NAV_ITEMS.map(({ to, icon: Icon, labelKey }) => (
          <NavLink
            key={to}
            to={to}
            className={({ isActive }) =>
              cn(
                "flex h-10 items-center gap-3 rounded-md px-3 text-sm transition-colors",
                "focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring",
                isActive
                  ? "bg-accent font-medium text-accent-foreground"
                  : "text-muted-foreground hover:bg-accent hover:text-accent-foreground"
              )
            }
          >
            <Icon className="h-4 w-4 shrink-0" aria-hidden="true" />
            {t(labelKey)}
          </NavLink>
        ))}
      </nav>
    </aside>
  );
}
