import type { ConfirmationResult, RecaptchaVerifier } from "firebase/auth";
import { Loader2 } from "lucide-react";
import { type FormEvent, useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";

import { fieldClass } from "@/components/profile/styles";
import { Button } from "@/components/ui/button";
import { useAuth } from "@/hooks/useAuth";
import { useI18n } from "@/hooks/useI18n";
import {
  authErrorKey,
  confirmReauthCode,
  createRecaptchaVerifier,
  disposeRecaptchaVerifier,
  reauthenticateWithGoogle,
  sendReauthCode,
  signInMethod,
  signOut,
} from "@/services/authService";

export interface ReauthPanelProps {
  /** Called once the person has signed in again; the caller carries on with the deletion. */
  onConfirmed: () => void;
  onCancel: () => void;
}

/** "Confirm it's you": the same sign-in method again, so a stranger on a shared phone cannot delete. */
export default function ReauthPanel({ onConfirmed, onCancel }: ReauthPanelProps) {
  const { t } = useI18n();
  const { user } = useAuth();
  const navigate = useNavigate();
  const method = signInMethod();
  const phone = user?.phoneNumber ?? "";

  const [confirmation, setConfirmation] = useState<ConfirmationResult | null>(null);
  const [code, setCode] = useState("");
  const [busy, setBusy] = useState(false);
  const [errorKey, setErrorKey] = useState<string | null>(null);
  const recaptchaHostRef = useRef<HTMLDivElement>(null);
  const verifierRef = useRef<RecaptchaVerifier | null>(null);

  useEffect(
    () => () => {
      if (verifierRef.current !== null) {
        disposeRecaptchaVerifier(verifierRef.current);
        verifierRef.current = null;
      }
    },
    []
  );

  async function run(task: () => Promise<void>) {
    setBusy(true);
    setErrorKey(null);
    try {
      await task();
    } catch (error) {
      if (import.meta.env.DEV) {
        console.warn("Sign-in confirmation failed:", error);
      }
      setErrorKey(authErrorKey(error));
      setBusy(false);
    }
  }

  function freshVerifier(): RecaptchaVerifier {
    if (verifierRef.current !== null) {
      disposeRecaptchaVerifier(verifierRef.current);
    }
    const element = document.createElement("div");
    recaptchaHostRef.current?.replaceChildren(element);
    verifierRef.current = createRecaptchaVerifier(element);
    return verifierRef.current;
  }

  // Without this, ProtectedRoute would catch the signed-out state and redirect to /sign-in
  // instead of the public landing page.
  async function handleSignOut() {
    await signOut();
    navigate("/", { replace: true });
  }

  function sendCode() {
    void run(async () => {
      setConfirmation(await sendReauthCode(freshVerifier()));
      setCode("");
      setBusy(false);
    });
  }

  function handleCodeSubmit(event: FormEvent) {
    event.preventDefault();
    if (confirmation !== null) {
      void run(async () => {
        await confirmReauthCode(confirmation, code);
        onConfirmed();
      });
    }
  }

  const spinner = <Loader2 className="mr-2 h-4 w-4 animate-spin" aria-hidden="true" />;

  return (
    <div
      className="space-y-4 rounded-md border border-input bg-muted/40 p-4"
      role="group"
      aria-labelledby="reauth-title"
    >
      <h3 id="reauth-title" className="font-semibold">
        {t("profile.delete.reauthTitle")}
      </h3>
      <p className="text-sm text-muted-foreground">{t("profile.delete.reauthBody")}</p>

      {method === "google" && (
        <Button
          variant="outline"
          size="lg"
          className="h-11 w-full"
          disabled={busy}
          onClick={() =>
            void run(async () => {
              await reauthenticateWithGoogle();
              onConfirmed();
            })
          }
        >
          {busy && spinner}
          {t("profile.delete.reauthGoogle")}
        </Button>
      )}

      {method === "phone" && confirmation === null && (
        <Button size="lg" className="h-11 w-full" disabled={busy} onClick={sendCode}>
          {busy && spinner}
          {t("profile.delete.reauthSendCode", { phone })}
        </Button>
      )}

      {method === "phone" && confirmation !== null && (
        <form onSubmit={handleCodeSubmit} className="space-y-3">
          <label htmlFor="reauth-code" className="text-sm font-bold">
            {t("profile.delete.codeLabel")}
          </label>
          <input
            id="reauth-code"
            inputMode="numeric"
            autoComplete="one-time-code"
            maxLength={6}
            value={code}
            onChange={(event) => setCode(event.target.value.replace(/\D/g, ""))}
            className={fieldClass}
          />
          <Button
            type="submit"
            variant="destructive"
            size="lg"
            className="h-11 w-full"
            disabled={busy || code.length !== 6}
          >
            {busy && spinner}
            {t("profile.delete.reauthConfirm")}
          </Button>
        </form>
      )}

      {method === "other" && (
        <Button
          variant="outline"
          size="lg"
          className="h-11 w-full"
          onClick={() => void handleSignOut()}
        >
          {t("auth.signOut")}
        </Button>
      )}

      {errorKey !== null && (
        <p role="alert" className="text-sm text-danger-ink">
          {t(errorKey)}
        </p>
      )}

      <div ref={recaptchaHostRef} />
      <Button variant="ghost" className="h-11 w-full" disabled={busy} onClick={onCancel}>
        {t("profile.delete.cancel")}
      </Button>
    </div>
  );
}
