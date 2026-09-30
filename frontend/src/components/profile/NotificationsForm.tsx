import { type FormEvent, useState } from "react";

import { inputClass, sectionClass } from "@/components/profile/styles";
import SaveStatus from "@/components/profile/SaveStatus";
import { Button } from "@/components/ui/button";
import { useI18n } from "@/hooks/useI18n";
import { useEnablePush, usePushPermission } from "@/hooks/useNotifications";
import { useUpdateProfile } from "@/hooks/useUser";
import i18n from "@/lib/i18n";
import { CORRIDOR_IDS } from "@/types/enums";
import type { UserProfile } from "@/types/user";
import { countryName } from "@/utils/format";

/**
 * Push permission is a one-time browser prompt, separate from the form's own save cycle
 * below: it takes effect immediately, is not part of `notification_prefs`, and "unsupported"
 * (not configured, or the browser has no Notification API) shows nothing rather than an
 * error — that is this feature's normal state until Firebase Cloud Messaging is set up.
 */
function PushStatus() {
  const { t } = useI18n();
  const permission = usePushPermission();
  const enable = useEnablePush();

  if (permission === "unsupported") {
    return null;
  }
  if (permission === "granted") {
    return <p className="text-sm text-muted-foreground">{t("profile.notifications.pushOn")}</p>;
  }
  if (permission === "denied") {
    return <p className="text-sm text-muted-foreground">{t("profile.notifications.pushDenied")}</p>;
  }
  return (
    <div className="space-y-2">
      <Button
        type="button"
        variant="outline"
        className="h-11"
        onClick={() => enable.mutate()}
        disabled={enable.isPending}
      >
        {t("profile.notifications.pushEnable")}
      </Button>
      {enable.isSuccess && enable.data === null && (
        <p className="text-sm text-muted-foreground">{t("profile.notifications.pushDeclined")}</p>
      )}
    </div>
  );
}

interface Draft {
  radar_alerts: boolean;
  reminders: boolean;
  radar_corridors: string[];
}

/**
 * What the profile holds, or the documented default: everything on, for the person's own
 * corridor (host to home). The default is only shown; nothing is written until they save.
 */
function savedValues(profile: UserProfile): Draft {
  const own = `${profile.host_country ?? ""}-${profile.home_country ?? ""}`;
  const prefs = profile.notification_prefs;
  return {
    radar_alerts: prefs?.radar_alerts ?? true,
    reminders: prefs?.reminders ?? true,
    radar_corridors: prefs?.radar_corridors ?? CORRIDOR_IDS.filter((id) => id === own),
  };
}

function sameSet(a: string[], b: string[]): boolean {
  return a.length === b.length && a.every((id) => b.includes(id));
}

export interface NotificationsFormProps {
  profile: UserProfile;
}

export default function NotificationsForm({ profile }: NotificationsFormProps) {
  const { t } = useI18n();
  const save = useUpdateProfile();
  const saved = savedValues(profile);
  // Only what the person changed, kept on top of what is saved. Starting from a full copy
  // would go stale: the default corridor follows the profile's countries, which the details
  // form can change, and the untouched form would then wrongly look edited.
  const [edits, setEdits] = useState<Partial<Draft>>({});
  const draft: Draft = { ...saved, ...edits };
  const language = i18n.resolvedLanguage ?? "en";

  const dirty =
    draft.radar_alerts !== saved.radar_alerts ||
    draft.reminders !== saved.reminders ||
    !sameSet(draft.radar_corridors, saved.radar_corridors);

  function toggleCorridor(id: string, on: boolean) {
    const others = draft.radar_corridors.filter((existing) => existing !== id);
    setEdits({ ...edits, radar_corridors: on ? [...others, id] : others });
  }

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    if (dirty) {
      // The whole map is written each time, so Firestore always holds a complete answer.
      save.mutate(
        { notification_prefs: { ...draft } },
        // Firestore now holds these values, so the form goes back to following the profile.
        { onSuccess: () => setEdits({}) }
      );
    }
  }

  return (
    <form onSubmit={handleSubmit} className={sectionClass} aria-labelledby="notifications-heading">
      <h2 id="notifications-heading" className="text-lg font-semibold">
        {t("profile.notifications.heading")}
      </h2>

      <PushStatus />

      <label className="flex min-h-11 cursor-pointer items-start gap-3 text-base">
        <input
          type="checkbox"
          checked={draft.radar_alerts}
          onChange={(event) => setEdits({ ...edits, radar_alerts: event.target.checked })}
          disabled={save.isPending}
          className={`${inputClass} mt-1`}
        />
        <span>{t("profile.notifications.radarAlerts")}</span>
      </label>

      <fieldset className="space-y-2" disabled={!draft.radar_alerts || save.isPending}>
        <legend className="text-sm font-medium">{t("profile.notifications.corridors")}</legend>
        <p className="text-xs text-muted-foreground">{t("profile.notifications.corridorsHint")}</p>
        <div className="grid gap-2 sm:grid-cols-2">
          {CORRIDOR_IDS.map((id) => {
            const [host, home] = id.split("-");
            return (
              <label
                key={id}
                className="flex min-h-11 cursor-pointer items-center gap-3 rounded-md border border-input px-3 text-base has-[:disabled]:opacity-50"
              >
                <input
                  type="checkbox"
                  checked={draft.radar_corridors.includes(id)}
                  onChange={(event) => toggleCorridor(id, event.target.checked)}
                  className={inputClass}
                />
                <span>
                  {countryName(host, language)} → {countryName(home, language)}
                </span>
              </label>
            );
          })}
        </div>
      </fieldset>

      <label className="flex min-h-11 cursor-pointer items-start gap-3 text-base">
        <input
          type="checkbox"
          checked={draft.reminders}
          onChange={(event) => setEdits({ ...edits, reminders: event.target.checked })}
          disabled={save.isPending}
          className={`${inputClass} mt-1`}
        />
        <span>{t("profile.notifications.reminders")}</span>
      </label>

      <div className="space-y-2">
        <Button
          type="submit"
          size="lg"
          className="h-11 w-full sm:w-auto"
          disabled={!dirty || save.isPending}
        >
          {t("profile.save")}
        </Button>
        <SaveStatus
          saving={save.isPending}
          failed={save.isError}
          saved={save.isSuccess && !dirty}
        />
      </div>
    </form>
  );
}
