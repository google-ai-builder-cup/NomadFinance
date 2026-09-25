import { LogOut } from "lucide-react";
import { type FormEvent, useEffect, useRef, useState } from "react";
import { Navigate, useNavigate } from "react-router-dom";

import LoadingSpinner from "@/components/common/LoadingSpinner";
import { Button } from "@/components/ui/button";
import { useI18n } from "@/hooks/useI18n";
import { useCompleteOnboarding, useUserProfile } from "@/hooks/useUser";
import { trackOnboardingCompleted } from "@/lib/analytics";
import i18n from "@/lib/i18n";
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
        className="mx-auto flex min-h-screen max-w-sm flex-col items-center justify-center gap-4 px-4 text-center"
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
      void i18n.changeLanguage(value);
    }
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
    <main className="mx-auto flex min-h-screen w-full max-w-md flex-col gap-6 px-4 py-6">
      <header className="space-y-4">
        <div className="flex items-center justify-between">
          <span className="text-lg font-bold tracking-tight">NomadFinance</span>
          <Button
            variant="ghost"
            size="icon"
            aria-label={t("auth.signOut")}
            title={t("auth.signOut")}
            onClick={() => void signOut()}
          >
            <LogOut className="h-4 w-4" aria-hidden="true" />
          </Button>
        </div>
        <h1 className="text-2xl font-bold tracking-tight">{t("onboarding.title")}</h1>
        <div className="space-y-2">
          <p className="text-xs text-muted-foreground">{progressLabel}</p>
          <div
            role="progressbar"
            aria-label={progressLabel}
            aria-valuemin={1}
            aria-valuemax={STEPS.length}
            aria-valuenow={stepIndex + 1}
            className="h-2 overflow-hidden rounded-full bg-secondary"
          >
            <div
              className="h-full rounded-full bg-primary transition-all"
              style={{ width: `${((stepIndex + 1) / STEPS.length) * 100}%` }}
            />
          </div>
        </div>
      </header>

      <form onSubmit={handleSubmit} className="flex flex-1 flex-col gap-6">
        <fieldset className="space-y-4" aria-describedby="onboarding-hint">
          <legend
            ref={questionRef}
            tabIndex={-1}
            className="text-xl font-semibold focus:outline-none"
          >
            {t(`onboarding.steps.${step.id}.question`)}
          </legend>
          <p id="onboarding-hint" className="text-sm text-muted-foreground">
            {t(`onboarding.steps.${step.id}.hint`)}
          </p>
          <div className="grid gap-2 sm:grid-cols-2">
            {options.map((option) => (
              <label
                key={option.value}
                className={cn(
                  "flex min-h-12 cursor-pointer items-center gap-3 rounded-lg border px-4 py-3 text-base transition-colors",
                  "has-[:focus-visible]:ring-1 has-[:focus-visible]:ring-ring",
                  selected === option.value
                    ? "border-primary bg-accent font-medium"
                    : "border-input hover:bg-accent"
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
          <p role="alert" className="text-center text-sm text-destructive">
            {t("onboarding.saveError")}
          </p>
        )}

        <div className="mt-auto flex gap-3">
          {stepIndex > 0 && (
            <Button
              type="button"
              variant="outline"
              size="lg"
              className="h-11 flex-1"
              disabled={save.isPending}
              onClick={() => setStepIndex((index) => index - 1)}
            >
              {t("onboarding.back")}
            </Button>
          )}
          <Button
            type="submit"
            size="lg"
            className="h-11 flex-1"
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
    </main>
  );
}
