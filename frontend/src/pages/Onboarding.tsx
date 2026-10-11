import { LogOut } from "lucide-react";
import { type FormEvent, useEffect, useRef, useState } from "react";
import { Navigate, useNavigate } from "react-router-dom";

import LoadingSpinner from "@/components/common/LoadingSpinner";
import AuthSplit from "@/components/layout/AuthSplit";
import { Button } from "@/components/ui/button";
import { useI18n } from "@/hooks/useI18n";
import { useCompleteOnboarding, useUserProfile } from "@/hooks/useUser";
import { trackOnboardingCompleted } from "@/lib/analytics";
import i18n, { setLanguage } from "@/lib/i18n";
import { SUPPORTED_LANGUAGES } from "@/lib/languages";
import { cn } from "@/lib/utils";
import { signOut } from "@/services/authService";
import { isOnboarded } from "@/services/userService";
import { HOME_COUNTRIES, HOST_COUNTRIES, isLanguageCode, JOB_TYPES } from "@/types/enums";
import type { OnboardingAnswers } from "@/types/user";
import { countryName } from "@/utils/format";

// Language first, so every later question is already in the worker's language.
const STEPS = [
  { id: "language", field: "preferred_language" },
  { id: "hostCountry", field: "host_country" },
  { id: "homeCountry", field: "home_country" },
  { id: "jobType", field: "job_type" },
] as const;

interface Option {
  value: string;
  label: string;
}

function isComplete(answers: Partial<OnboardingAnswers>): answers is OnboardingAnswers {
  return STEPS.every(({ field }) => answers[field] !== undefined);
}

export default function Onboarding() {
  const { t } = useI18n();
  const navigate = useNavigate();
  const profile = useUserProfile();
  const save = useCompleteOnboarding();
  const [stepIndex, setStepIndex] = useState(0);
  const [answers, setAnswers] = useState<Partial<OnboardingAnswers>>(() =>
    isLanguageCode(i18n.resolvedLanguage) ? { preferred_language: i18n.resolvedLanguage } : {}
  );
  const questionRef = useRef<HTMLLegendElement>(null);

  // Move focus to the new question so screen readers announce it.
  useEffect(() => {
    questionRef.current?.focus();
  }, [stepIndex]);

  if (profile.isPending) {
    return <LoadingSpinner label={t("common.loading")} fullScreen />;
  }
  // Without the profile we can't tell create from update, so don't offer the form.
  if (profile.isError) {
    return (
      <div
        role="alert"
        className="mx-auto flex min-h-screen min-h-dvh max-w-sm flex-col items-center justify-center gap-4 px-4 text-center"
      >
        <p className="text-sm text-muted-foreground">{t("onboarding.loadError")}</p>
        <Button onClick={() => void profile.refetch()}>{t("common.retry")}</Button>
      </div>
    );
  }
  if (isOnboarded(profile.data)) {
    return <Navigate to="/dashboard" replace />;
  }

  const step = STEPS[stepIndex];
  const language = i18n.resolvedLanguage ?? "en";
  const selected = answers[step.field];
  const isLast = stepIndex === STEPS.length - 1;

  const options: Option[] = {
    language: SUPPORTED_LANGUAGES.map(({ code, nativeName }) => ({
      value: code,
      label: nativeName,
    })),
    hostCountry: HOST_COUNTRIES.map((code) => ({
      value: code,
      label: countryName(code, language),
    })),
    homeCountry: HOME_COUNTRIES.map((code) => ({
      value: code,
      label: countryName(code, language),
    })),
    jobType: JOB_TYPES.map((id) => ({ value: id, label: t(`onboarding.jobTypes.${id}`) })),
  }[step.id];

  function choose(value: string) {
    setAnswers((previous) => ({ ...previous, [step.field]: value }));
    if (step.id === "language") {
      void setLanguage(value);
    }
  }

  // Without this, ProtectedRoute would catch the signed-out state and redirect to /sign-in
  // instead of the public landing page.
  async function handleSignOut() {
    await signOut();
    navigate("/", { replace: true });
  }

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    if (!isLast) {
      setStepIndex((index) => index + 1);
      return;
    }
    if (isComplete(answers)) {
      save.mutate(answers, {
        onSuccess: () => {
          trackOnboardingCompleted();
          navigate("/dashboard", { replace: true });
        },
      });
    }
  }

  const progressLabel = t("onboarding.progress", { current: stepIndex + 1, total: STEPS.length });

  return (
    <AuthSplit>
      <header className="space-y-4">
        <div className="flex items-center justify-between">
          <p className="text-xs font-bold uppercase tracking-widest text-primary">
            {progressLabel}
          </p>
          <Button
            variant="ghost"
            size="icon"
            aria-label={t("auth.signOut")}
            title={t("auth.signOut")}
            onClick={() => void handleSignOut()}
          >
            <LogOut className="h-4 w-4" aria-hidden="true" />
          </Button>
        </div>
        <h1 className="text-3xl font-extrabold leading-tight tracking-tight">
          {t("onboarding.title")}
        </h1>
        <div
          role="progressbar"
          aria-label={progressLabel}
          aria-valuemin={1}
          aria-valuemax={STEPS.length}
          aria-valuenow={stepIndex + 1}
          className="flex items-center gap-2"
        >
          {STEPS.map(({ id }, index) => (
            <div key={id} className="flex flex-1 items-center gap-2 last:flex-none">
              <span
                aria-hidden="true"
                className={cn(
                  "grid h-8 w-8 shrink-0 place-items-center rounded-full text-xs font-extrabold transition-all duration-base",
                  index < stepIndex && "bg-safe text-white",
                  index === stepIndex &&
                    "scale-110 bg-primary text-primary-foreground ring-4 ring-primary/20",
                  index > stepIndex && "bg-muted text-muted-foreground"
                )}
              >
                {index < stepIndex ? "✓" : index + 1}
              </span>
              {index < STEPS.length - 1 && (
                <span
                  aria-hidden="true"
                  className={cn(
                    "h-1 flex-1 rounded-full transition-colors duration-slow",
                    index < stepIndex ? "bg-safe" : "bg-muted"
                  )}
                />
              )}
            </div>
          ))}
        </div>
      </header>

      <form onSubmit={handleSubmit} className="flex flex-1 flex-col gap-6">
        <fieldset
          key={step.id}
          className="animate-fade-up space-y-4"
          aria-describedby="onboarding-hint"
        >
          <legend ref={questionRef} tabIndex={-1} className="text-xl font-bold focus:outline-none">
            {t(`onboarding.steps.${step.id}.question`)}
          </legend>
          <p id="onboarding-hint" className="text-sm text-muted-foreground">
            {t(`onboarding.steps.${step.id}.hint`)}
          </p>
          <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
            {options.map((option) => (
              <label
                key={option.value}
                className={cn(
                  "flex min-h-14 cursor-pointer items-center gap-3 rounded-xl border px-4 py-3 text-base transition-all duration-base",
                  "has-[:focus-visible]:ring-2 has-[:focus-visible]:ring-ring",
                  selected === option.value
                    ? "border-primary bg-accent font-bold shadow-sm"
                    : "border-input bg-card hover:bg-accent"
                )}
              >
                <input
                  type="radio"
                  name={step.id}
                  value={option.value}
                  checked={selected === option.value}
                  onChange={() => choose(option.value)}
                  disabled={save.isPending}
                  className="h-4 w-4 accent-primary"
                />
                <span>{option.label}</span>
              </label>
            ))}
          </div>
        </fieldset>

        {save.isError && (
          <p role="alert" className="text-center text-sm text-danger-ink">
            {t("onboarding.saveError")}
          </p>
        )}

        <div className="mt-auto flex gap-3">
          {stepIndex > 0 && (
            <Button
              type="button"
              variant="outline"
              size="lg"
              className="h-12 flex-1 rounded-xl font-bold"
              disabled={save.isPending}
              onClick={() => setStepIndex((index) => index - 1)}
            >
              {t("onboarding.back")}
            </Button>
          )}
          <Button
            type="submit"
            size="lg"
            className="h-12 flex-1 rounded-xl font-bold"
            disabled={selected === undefined || save.isPending}
          >
            {!isLast
              ? t("onboarding.next")
              : save.isPending
                ? t("onboarding.saving")
                : t("onboarding.finish")}
          </Button>
        </div>
      </form>
    </AuthSplit>
  );
}
