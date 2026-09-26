import { useEffect } from "react";

import { useInstallPrompt } from "@/hooks/useInstallPrompt";
import { dismissToast, toast } from "@/hooks/useToast";
import { canAddToIosHomeScreen } from "@/utils/platform";

const DISMISSED_AT_KEY = "nomadfinance.installOfferDismissedAt";
// Asking on every visit is nagging; never asking again loses people who change their mind
// (and phones are often shared).
const ASK_AGAIN_AFTER_MS = 14 * 24 * 60 * 60 * 1000;
// Let the page appear first, so the offer doesn't cover it while it is loading.
const SHOW_DELAY_MS = 3000;
const TOAST_ID = "app-install";

function recentlyDismissed(): boolean {
  try {
    return Date.now() - Number(localStorage.getItem(DISMISSED_AT_KEY)) < ASK_AGAIN_AFTER_MS;
  } catch {
    return false;
  }
}

function rememberDismissed(): void {
  try {
    localStorage.setItem(DISMISSED_AT_KEY, String(Date.now()));
  } catch {
    // Storage blocked (private mode): the offer may come back on the next visit.
  }
}

/**
 * Offers to install the app, as a toast on any page, signed in or not. Chrome, Edge and
 * Android get an Install button (the browser's own dialog); iOS gets Share-menu steps,
 * because it has no install prompt. Closing the toast means "not now" for two weeks.
 * Renders nothing itself.
 */
export default function InstallPrompt() {
  const { canInstall, promptInstall } = useInstallPrompt();

  useEffect(() => {
    const ios = canAddToIosHomeScreen();
    if ((!canInstall && !ios) || recentlyDismissed()) {
      return;
    }
    const timer = window.setTimeout(() => {
      toast({
        id: TOAST_ID,
        messageKey: ios ? "pwa.installIos" : "pwa.installOffer",
        duration: null,
        action: ios
          ? undefined
          : {
              labelKey: "pwa.install",
              onClick: () =>
                void promptInstall().then((outcome) => {
                  if (outcome === "dismissed") {
                    rememberDismissed();
                  }
                }),
            },
        onDismiss: rememberDismissed,
      });
    }, SHOW_DELAY_MS);
    // Also runs once the app is installed (canInstall turns false): the offer goes away.
    return () => {
      window.clearTimeout(timer);
      dismissToast(TOAST_ID);
    };
  }, [canInstall, promptInstall]);

  return null;
}
