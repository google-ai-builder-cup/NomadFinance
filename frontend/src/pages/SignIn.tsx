import type { ConfirmationResult, RecaptchaVerifier } from "firebase/auth";
import { ArrowLeft, Loader2, Phone } from "lucide-react";
import { type FormEvent, useEffect, useRef, useState } from "react";
import { Navigate, useLocation } from "react-router-dom";

import LoadingSpinner from "@/components/common/LoadingSpinner";
import { Button } from "@/components/ui/button";
import { useAuth } from "@/hooks/useAuth";
import { useI18n } from "@/hooks/useI18n";
import {
  authErrorKey,
  confirmPhoneCode,
  createRecaptchaVerifier,
  disposeRecaptchaVerifier,
  redirectSignInErrorKey,
  sendPhoneCode,
  signInWithGoogle,
} from "@/services/authService";
import { PHONE_DIAL_CODES } from "@/utils/constants";
import { toE164 } from "@/utils/validators";

type BusyAction = "google" | "sendCode" | "verify";

const inputClass =
  "h-11 rounded-md border border-input bg-background px-3 text-base shadow-sm " +
  "focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring disabled:opacity-50";

export default function SignIn() {
  const { user, loading } = useAuth();
  const { t } = useI18n();
  const location = useLocation();
  const from = (location.state as { from?: { pathname: string } } | null)?.from?.pathname;

  const [dialCode, setDialCode] = useState(PHONE_DIAL_CODES[0].dialCode);
  const [localNumber, setLocalNumber] = useState("");
  const [sentTo, setSentTo] = useState("");
  const [code, setCode] = useState("");
  const [confirmation, setConfirmation] = useState<ConfirmationResult | null>(null);
  const [busy, setBusy] = useState<BusyAction | null>(null);
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

  useEffect(() => {
    let active = true;
    void redirectSignInErrorKey().then((key) => {
      if (active && key !== null) {
        setErrorKey(key);
      }
    });
    return () => {
      active = false;
    };
  }, []);

  if (loading) {
    return <LoadingSpinner label={t("common.loading")} fullScreen />;
  }
  // Also where a successful sign-in lands: AuthProvider updates `user`, this redirects.
  if (user) {
    return <Navigate to={from ?? "/dashboard"} replace />;
  }

  async function run(action: BusyAction, task: () => Promise<void>) {
    setBusy(action);
    setErrorKey(null);
    try {
      await task();
    } catch (error) {
      if (import.meta.env.DEV) {
        // The on-screen message is kept generic for users; the Firebase code is what you debug.
        console.warn("Sign-in failed:", error);
      }
      setErrorKey(authErrorKey(error));
    } finally {
      setBusy(null);
    }
  }

  function freshVerifier(): RecaptchaVerifier {
    if (verifierRef.current !== null) {
      disposeRecaptchaVerifier(verifierRef.current);
      verifierRef.current = null;
    }
    const element = document.createElement("div");
    recaptchaHostRef.current?.replaceChildren(element);
    verifierRef.current = createRecaptchaVerifier(element);
    return verifierRef.current;
  }

  function sendCode(phoneNumber: string) {
    void run("sendCode", async () => {
      setConfirmation(await sendPhoneCode(phoneNumber, freshVerifier()));
      setSentTo(phoneNumber);
      setCode("");
    });
  }

  function handlePhoneSubmit(event: FormEvent) {
    event.preventDefault();
    const phoneNumber = toE164(dialCode, localNumber);
    if (phoneNumber === null) {
      setErrorKey("auth.error.invalidPhone");
      return;
    }
    sendCode(phoneNumber);
  }

  function handleCodeSubmit(event: FormEvent) {
    event.preventDefault();
    if (confirmation !== null) {
      void run("verify", () => confirmPhoneCode(confirmation, code));
    }
  }

  function changeNumber() {
    setConfirmation(null);
    setCode("");
    setErrorKey(null);
  }

  const spinner = <Loader2 className="mr-2 h-4 w-4 animate-spin" aria-hidden="true" />;

  return (
    <main className="mx-auto flex min-h-screen w-full max-w-sm flex-col justify-center gap-6 px-4 py-10">
      <header className="space-y-2 text-center">
        <h1 className="text-2xl font-bold tracking-tight">{t("auth.signIn.title")}</h1>
        <p className="text-sm text-muted-foreground">{t("auth.signIn.subtitle")}</p>
      </header>

      <Button
        variant="outline"
        size="lg"
        className="h-11 w-full"
        disabled={busy !== null}
        onClick={() => void run("google", signInWithGoogle)}
      >
        {busy === "google" && spinner}
        {busy === "google" ? t("auth.signIn.signingIn") : t("auth.signIn.google")}
      </Button>

      <div className="flex items-center gap-3 text-xs uppercase text-muted-foreground">
        <span className="h-px flex-1 bg-border" aria-hidden="true" />
        {t("auth.signIn.or")}
        <span className="h-px flex-1 bg-border" aria-hidden="true" />
      </div>

      {confirmation === null ? (
        <form onSubmit={handlePhoneSubmit} className="space-y-3" noValidate>
          <label htmlFor="phone" className="block text-sm font-medium">
            {t("auth.signIn.phoneLabel")}
          </label>
          <div className="flex gap-2">
            <select
              aria-label={t("auth.signIn.countryCodeLabel")}
              className={inputClass}
              value={dialCode}
              disabled={busy !== null}
              onChange={(event) => setDialCode(event.target.value)}
            >
              {PHONE_DIAL_CODES.map((option) => (
                <option key={option.country} value={option.dialCode}>
                  {option.country} {option.dialCode}
                </option>
              ))}
            </select>
            <input
              id="phone"
              type="tel"
              inputMode="tel"
              autoComplete="tel-national"
              aria-describedby="phone-hint"
              className={`${inputClass} min-w-0 flex-1`}
              placeholder={t("auth.signIn.phonePlaceholder")}
              value={localNumber}
              disabled={busy !== null}
              onChange={(event) => setLocalNumber(event.target.value)}
            />
          </div>
          <p id="phone-hint" className="text-xs text-muted-foreground">
            {t("auth.signIn.phoneHint")}
          </p>
          <Button
            type="submit"
            size="lg"
            className="h-11 w-full"
            disabled={busy !== null || localNumber.trim() === ""}
          >
            {busy === "sendCode" ? spinner : <Phone className="mr-2 h-4 w-4" aria-hidden="true" />}
            {busy === "sendCode" ? t("auth.signIn.sendingCode") : t("auth.signIn.sendCode")}
          </Button>
        </form>
      ) : (
        <form onSubmit={handleCodeSubmit} className="space-y-3" noValidate>
          <p className="text-sm text-muted-foreground">
            {t("auth.signIn.codeSentTo", { phone: sentTo })}
          </p>
          <label htmlFor="otp" className="block text-sm font-medium">
            {t("auth.signIn.codeLabel")}
          </label>
          <input
            id="otp"
            inputMode="numeric"
            autoComplete="one-time-code"
            maxLength={6}
            autoFocus
            className={`${inputClass} w-full text-center text-lg tracking-[0.5em]`}
            value={code}
            disabled={busy !== null}
            onChange={(event) => setCode(event.target.value.replace(/\D/g, ""))}
          />
          <Button
            type="submit"
            size="lg"
            className="h-11 w-full"
            disabled={busy !== null || code.length !== 6}
          >
            {busy === "verify" && spinner}
            {busy === "verify" ? t("auth.signIn.verifying") : t("auth.signIn.verify")}
          </Button>
          <div className="flex justify-between">
            <Button type="button" variant="link" className="px-0" onClick={changeNumber}>
              <ArrowLeft className="mr-1 h-4 w-4" aria-hidden="true" />
              {t("auth.signIn.changeNumber")}
            </Button>
            <Button
              type="button"
              variant="link"
              className="px-0"
              disabled={busy !== null}
              onClick={() => sendCode(sentTo)}
            >
              {t("auth.signIn.resendCode")}
            </Button>
          </div>
        </form>
      )}

      {errorKey !== null && (
        <p role="alert" className="text-center text-sm text-destructive">
          {t(errorKey)}
        </p>
      )}

      {/* Invisible reCAPTCHA mounts here; freshVerifier() replaces its child on each attempt. */}
      <div ref={recaptchaHostRef} />
    </main>
  );
}
