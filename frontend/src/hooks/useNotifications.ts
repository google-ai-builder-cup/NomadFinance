import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect } from "react";
import { useNavigate } from "react-router-dom";

import { useAuth } from "@/hooks/useAuth";
import { toast } from "@/hooks/useToast";
import {
  listenForPushClicks,
  listenForPushes,
  pushPermission,
  requestPushToken,
} from "@/lib/messaging";
import {
  countUnreadNotifications,
  listNotifications,
  markNotificationRead,
  NOTIFICATIONS_PAGE_SIZE,
} from "@/services/notificationService";
import { saveFcmToken } from "@/services/userService";
import { isCoachCheckinPath, safeAppPath } from "@/utils/appLinks";

function notificationsKey(uid: string | undefined) {
  return ["notifications", uid] as const;
}

/**
 * The signed-in worker's newest notifications, newest first. `max` is how many the screen
 * shows: the dashboard widget asks for two instead of downloading the whole feed.
 */
export function useNotifications(max: number = NOTIFICATIONS_PAGE_SIZE) {
  const { user } = useAuth();
  const uid = user?.uid;
  return useQuery({
    queryKey: [...notificationsKey(uid), "list", max] as const,
    queryFn: () => listNotifications(uid ?? "", max),
    enabled: uid !== undefined,
    staleTime: 30_000,
  });
}

/** How many notifications are unread, for the dashboard's "N new alerts" line. */
export function useUnreadNotificationCount() {
  const { user } = useAuth();
  const uid = user?.uid;
  return useQuery({
    queryKey: [...notificationsKey(uid), "unread"] as const,
    queryFn: () => countUnreadNotifications(uid ?? ""),
    enabled: uid !== undefined,
    staleTime: 30_000,
  });
}

export function useMarkNotificationRead() {
  const { user } = useAuth();
  const queryClient = useQueryClient();
  const uid = user?.uid ?? "";
  return useMutation({
    mutationFn: (id: string) => markNotificationRead(uid, id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: notificationsKey(uid) }),
  });
}

/**
 * Whether push is on for this browser right now: "unsupported" covers not configured, no
 * browser support, and no Notification API — one state for all three, never an error to
 * handle. `Notification.permission` isn't itself reactive, but reading it fresh on every
 * render is enough here: the one caller (NotificationsForm) already re-renders when
 * `useEnablePush`'s mutation state changes, which is exactly when this needs to catch up.
 */
export function usePushPermission(): NotificationPermission | "unsupported" {
  return pushPermission();
}

/** Ask for permission and register this browser's push token, then save it to the profile. */
export function useEnablePush() {
  const { user } = useAuth();
  const uid = user?.uid ?? "";
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async () => {
      const token = await requestPushToken();
      if (token !== null) {
        await saveFcmToken(uid, token);
      }
      return token;
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["userProfile", uid] }),
  });
}

/**
 * Shows a toast for a push that arrives while the app is open and focused (a backgrounded
 * or closed tab is the service worker's job, public/firebase-messaging-sw.js). Call once,
 * from AppShell — matches useAnalytics()'s pattern in the same file.
 *
 * A generic message, not the push's own title/body: the toast system's messages are i18n
 * keys, translated live on a language switch, and a push's text already comes pre-translated
 * from the backend in the worker's own language — showing it here would need a second,
 * parallel "raw text" toast shape for this one caller. Opening the feed shows the real text.
 */
export function usePushSync(): void {
  const navigate = useNavigate();

  useEffect(() => {
    let unsubscribe: (() => void) | undefined;
    let cancelled = false;
    void listenForPushes((_title, _body, deepLink) => {
      // A Coach check-in opens its own questions; every other push is a Radar alert (NF-FC-022).
      const checkin = safeAppPath(deepLink);
      if (checkin !== null && isCoachCheckinPath(checkin)) {
        toast({
          messageKey: "toast.coachCheckin",
          action: { labelKey: "toast.coachCheckinAction", onClick: () => navigate(checkin) },
        });
        return;
      }
      toast({
        messageKey: "radar.alerts.pushToast",
        action: {
          labelKey: "radar.alerts.pushToastAction",
          onClick: () => navigate("/radar/alerts"),
        },
      });
    }).then((unsub) => {
      if (cancelled) {
        unsub();
      } else {
        unsubscribe = unsub;
      }
    });
    // A tap on a system notification while the app is open (the worker cannot navigate it itself).
    const stopClicks = listenForPushClicks((link) => navigate(link));
    return () => {
      cancelled = true;
      unsubscribe?.();
      stopClicks();
    };
  }, [navigate]);
}
