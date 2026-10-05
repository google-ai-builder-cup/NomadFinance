import { Outlet } from "react-router-dom";

import BottomNav from "@/components/layout/BottomNav";
import Footer from "@/components/layout/Footer";
import Header from "@/components/layout/Header";
import NavigationProgress from "@/components/layout/NavigationProgress";
import Sidebar from "@/components/layout/Sidebar";
import AnimatedBackground from "@/components/visual/AnimatedBackground";
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
      <NavigationProgress />
      <Header />
      <div className="flex flex-1">
        <Sidebar />
        {/* The bottom padding keeps the footer clear of the floating tab bar on phones. */}
        <div className="relative flex min-w-0 flex-1 flex-col pb-24 md:pb-0">
          {/* A faint dotted map behind the content only; every card on top stays solid. */}
          <AnimatedBackground variant="dotted-map" className="hidden opacity-40 lg:block" />
          <main
            id="main-content"
            tabIndex={-1}
            className="relative mx-auto w-full max-w-[84rem] flex-1 px-4 py-6 focus:outline-none md:px-8 md:py-8"
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
