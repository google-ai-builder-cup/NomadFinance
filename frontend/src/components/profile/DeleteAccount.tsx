import { useQueryClient } from "@tanstack/react-query";
import { Loader2 } from "lucide-react";
import { useState } from "react";
import { useNavigate } from "react-router-dom";

import ReauthPanel from "@/components/profile/ReauthPanel";
import { inputClass, sectionClass } from "@/components/profile/styles";
import { Button } from "@/components/ui/button";
import { useI18n } from "@/hooks/useI18n";
import {
  deleteAccount,
  isRecentLoginRequired,
  rememberAccountDeleted,
} from "@/services/accountService";
import { isApiConfigured } from "@/services/apiClient";
import { signedInWithin, signOut } from "@/services/authService";

type Stage = "idle" | "confirm" | "reauth" | "deleting";

// The backend accepts a sign-in up to 5 minutes old; ask again a little earlier so a slow
// confirmation screen never ends in a refusal.
const FRESH_SIGN_IN_SECONDS = 240;

const ITEM_KEYS = ["itemProfile", "itemContracts", "itemMoney", "itemFiles"] as const;

/** Danger zone at the bottom of the profile page. */
export default function DeleteAccount() {
  const { t } = useI18n();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [stage, setStage] = useState<Stage>("idle");
  const [understood, setUnderstood] = useState(false);
  const [failed, setFailed] = useState(false);

  // Without a reachable backend (a deployed site before CORS is set up) the button would only fail.
  if (!isApiConfigured) {
    return null;
  }

  function cancel() {
    setStage("idle");
    setUnderstood(false);
    setFailed(false);
  }

  async function runDeletion() {
    setStage("deleting");
    setFailed(false);
    try {
      await deleteAccount();
    } catch (error) {
      if (isRecentLoginRequired(error)) {
        setStage("reauth");
      } else {
        setFailed(true);
        setStage("confirm");
      }
      return;
    }
    // The account no longer exists. Sign out first so nothing tries to read it again.
    rememberAccountDeleted();
    await signOut().catch(() => undefined);
    queryClient.clear();
    navigate("/sign-in", { replace: true });
  }

  async function handleContinue() {
    if (await signedInWithin(FRESH_SIGN_IN_SECONDS)) {
      await runDeletion();
    } else {
      setStage("reauth");
    }
  }

  return (
    <section className={`${sectionClass} border-destructive/40`} aria-labelledby="delete-heading">
      <h2 id="delete-heading" className="text-lg font-semibold text-destructive">
        {t("profile.delete.heading")}
      </h2>
      <div className="space-y-2 text-sm">
        <p>{t("profile.delete.intro")}</p>
        <ul className="list-disc space-y-1 pl-5">
          {ITEM_KEYS.map((key) => (
            <li key={key}>{t(`profile.delete.${key}`)}</li>
          ))}
        </ul>
        <p className="text-muted-foreground">{t("profile.delete.radarNote")}</p>
      </div>

      {stage === "idle" && (
        <Button
          variant="outline"
          className="h-11 w-full border-destructive text-destructive sm:w-auto"
          onClick={() => setStage("confirm")}
        >
          {t("profile.delete.start")}
        </Button>
      )}

      {(stage === "confirm" || stage === "deleting") && (
        <div className="space-y-4">
          <label className="flex min-h-11 cursor-pointer items-start gap-3 text-base">
            <input
              type="checkbox"
              checked={understood}
              onChange={(event) => setUnderstood(event.target.checked)}
              disabled={stage === "deleting"}
              className={`${inputClass} mt-1`}
            />
            <span>{t("profile.delete.confirmLabel")}</span>
          </label>
          {failed && (
            <p role="alert" className="text-sm text-destructive">
              {t("profile.delete.error")}
            </p>
          )}
          <div className="flex flex-col gap-3 sm:flex-row">
            <Button
              variant="destructive"
              size="lg"
              className="h-11"
              disabled={!understood || stage === "deleting"}
              onClick={() => void handleContinue()}
            >
              {stage === "deleting" && (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" aria-hidden="true" />
              )}
              {stage === "deleting" ? t("profile.delete.deleting") : t("profile.delete.confirm")}
            </Button>
            <Button
              variant="outline"
              size="lg"
              className="h-11"
              disabled={stage === "deleting"}
              onClick={cancel}
            >
              {t("profile.delete.cancel")}
            </Button>
          </div>
        </div>
      )}

      {stage === "reauth" && (
        <ReauthPanel onConfirmed={() => void runDeletion()} onCancel={cancel} />
      )}
    </section>
  );
}
