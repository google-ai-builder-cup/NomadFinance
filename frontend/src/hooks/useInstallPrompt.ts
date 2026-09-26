import { useCallback, useEffect, useState } from "react";

export type InstallOutcome = "accepted" | "dismissed";

interface BeforeInstallPromptEvent extends Event {
  prompt(): Promise<void>;
  userChoice: Promise<{ outcome: InstallOutcome }>;
}

/**
 * Wraps the browser's `beforeinstallprompt` flow. Chrome/Edge/Android only —
 * iOS Safari never fires this event, so `canInstall` stays false there.
 */
export function useInstallPrompt(): {
  canInstall: boolean;
  /** Shows the browser's install dialog; resolves to the person's choice (null if unavailable). */
  promptInstall: () => Promise<InstallOutcome | null>;
} {
  const [deferredEvent, setDeferredEvent] = useState<BeforeInstallPromptEvent | null>(null);

  useEffect(() => {
    function handleBeforeInstallPrompt(event: Event) {
      event.preventDefault();
      setDeferredEvent(event as BeforeInstallPromptEvent);
    }
    function handleAppInstalled() {
      setDeferredEvent(null);
    }

    window.addEventListener("beforeinstallprompt", handleBeforeInstallPrompt);
    window.addEventListener("appinstalled", handleAppInstalled);
    return () => {
      window.removeEventListener("beforeinstallprompt", handleBeforeInstallPrompt);
      window.removeEventListener("appinstalled", handleAppInstalled);
    };
  }, []);

  const promptInstall = useCallback(async () => {
    if (!deferredEvent) {
      return null;
    }
    await deferredEvent.prompt();
    const { outcome } = await deferredEvent.userChoice;
    setDeferredEvent(null);
    return outcome;
  }, [deferredEvent]);

  return { canInstall: deferredEvent !== null, promptInstall };
}
