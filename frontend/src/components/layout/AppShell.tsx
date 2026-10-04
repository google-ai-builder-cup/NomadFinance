import { Outlet } from "react-router-dom";

import BottomNav from "@/components/layout/BottomNav";
import Footer from "@/components/layout/Footer";
import Header from "@/components/layout/Header";
import Sidebar from "@/components/layout/Sidebar";
import { useAnalytics } from "@/hooks/useAnalytics";
import { useI18n } from "@/hooks/useI18n";
import { usePushSync } from "@/hooks/useNotifications";

/** Layout route for every signed-in page: header, navigation, footer and the page itself. */
export default function AppShell() {
  const { t } = useI18n();
  useAnalytics();
  usePushSync();

  return (
    <div className="flex min-h-screen min-h-dvh flex-col">
      <a
        href="#main-content"
        className="sr-only focus:not-sr-only focus:absolute focus:left-2 focus:top-2 focus:z-50 focus:rounded-md focus:bg-background focus:px-3 focus:py-2 focus:text-sm focus:shadow"
      >
        {t("layout.skipToContent")}
      </a>
      <Header />
      <div className="flex flex-1">
        <Sidebar />
        {/* The bottom padding keeps the footer clear of the fixed tab bar on phones. */}
        <div className="flex min-w-0 flex-1 flex-col pb-16 md:pb-0">
          <main
            id="main-content"
            tabIndex={-1}
            className="mx-auto w-full max-w-4xl flex-1 px-4 py-6 focus:outline-none md:px-8 md:py-8"
          >
            <Outlet />
          </main>
          <Footer />
        </div>
      </div>
      <BottomNav />
    </div>
  );
}
