import { Bell } from "lucide-react";
import { Link, useLocation } from "react-router-dom";

import AccountMenu from "@/components/layout/AccountMenu";
import LanguageSelector from "@/components/layout/LanguageSelector";
import { HOME_ITEM, NAV_ITEMS, pillarForPath } from "@/components/layout/navItems";
import ThemeToggle from "@/components/layout/ThemeToggle";
import BrandMark from "@/components/visual/BrandMark";
import { useI18n } from "@/hooks/useI18n";
import { useUnreadNotificationCount } from "@/hooks/useNotifications";

/** The title of the page the worker is on, from the same nav list the sidebar reads. */
function useCrumb(pathname: string): { section: string | null; title: string } {
  const { t } = useI18n();
  const pillar = pillarForPath(pathname);
  if (pillar) {
    return { section: t("layout.crumbTools"), title: t(pillar.nameKey) };
  }
  const item = NAV_ITEMS.find(({ to }) => pathname === to) ?? HOME_ITEM;
  // Home is its own top level: a "Home / Home" trail would only repeat itself.
  return {
    section: pathname === HOME_ITEM.to ? null : t("layout.crumbHome"),
    title: pathname === "/profile" ? t("nav.profile") : t(item.labelKey),
  };
}

export default function Header() {
  const { t } = useI18n();
  const { pathname } = useLocation();
  const crumb = useCrumb(pathname);
  // A failed count only hides the badge; the bell still opens the alerts page.
  const unread = useUnreadNotificationCount().data ?? 0;

  return (
    <header className="glass sticky top-0 z-40 border-b pt-[env(safe-area-inset-top)]">
      <div className="flex h-16 items-center justify-between gap-3 px-4 md:px-6">
        <div className="flex min-w-0 items-center gap-4">
          <Link
            to="/dashboard"
            className="flex shrink-0 items-center gap-2.5 rounded-lg text-lg font-extrabold tracking-tight"
          >
            <BrandMark size={32} />
            <span className="hidden sm:inline">NomadFinance</span>
          </Link>
          <div className="hidden min-w-0 border-l pl-4 lg:block">
            {crumb.section && (
              <p className="text-xs font-medium text-muted-foreground">{crumb.section}</p>
            )}
            <p className="truncate text-sm font-bold leading-tight">{crumb.title}</p>
          </div>
        </div>
        <div className="flex min-w-0 items-center gap-2">
          <LanguageSelector />
          <ThemeToggle />
          <Link
            to="/radar/alerts"
            aria-label={
              unread > 0 ? t("layout.alertsUnread", { count: unread }) : t("layout.alerts")
            }
            className="relative flex h-11 w-11 items-center justify-center rounded-xl border bg-card shadow-sm transition-colors hover:bg-accent sm:h-10 sm:w-10"
          >
            <Bell className="h-4 w-4" aria-hidden="true" />
            {unread > 0 && (
              <span
                aria-hidden="true"
                className="absolute -right-1.5 -top-1.5 flex h-5 min-w-5 items-center justify-center rounded-full border-2 border-background bg-danger px-1 text-[11px] font-bold leading-none text-white"
              >
                {unread > 9 ? "9+" : unread}
              </span>
            )}
          </Link>
          <AccountMenu />
        </div>
      </div>
    </header>
  );
}
