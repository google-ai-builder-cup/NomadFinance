import { type FormEvent, useState } from "react";

import EvidencePicker from "@/components/radar/EvidencePicker";
import { Button } from "@/components/ui/button";
import { useI18n } from "@/hooks/useI18n";
import i18n from "@/lib/i18n";
import { SUPPORTED_LANGUAGES } from "@/lib/languages";
import { cn } from "@/lib/utils";
import {
  CORRIDOR_IDS,
  type CorridorId,
  HOST_COUNTRIES,
  type HostCountry,
  type LanguageCode,
} from "@/types/enums";
import { ENTITY_TYPES, type RadarReportRequest, type ReportDraft } from "@/types/radar";
import { countryName } from "@/utils/format";
import {
  buildRequest,
  MAX_DESCRIPTION_CHARS,
  MAX_NAME_CHARS,
  MIN_DESCRIPTION_CHARS,
  STEPS,
  stepProblem,
} from "@/utils/radarForm";

const fieldClass =
  "h-12 w-full rounded-xl border border-input bg-card px-3 text-base shadow-sm " +
  "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:opacity-50";

export interface ReportFormProps {
  /** The worker's own values, used until they pick something else. */
  defaults: {
    language: LanguageCode;
    hostCountry: HostCountry | null;
    corridorId: CorridorId | null;
  };
  pending: boolean;
  /** i18n key of why the last submit failed, shown next to the button. */
  errorKey: string | null;
  onSubmit: (request: RadarReportRequest, files: File[]) => void;
}

/** Four steps: who, where, what happened, then evidence and a last look before sending. */
export default function ReportForm({ defaults, pending, errorKey, onSubmit }: ReportFormProps) {
  const { t } = useI18n();
  const uiLanguage = i18n.resolvedLanguage ?? "en";
  const [stepIndex, setStepIndex] = useState(0);
  const [problemKey, setProblemKey] = useState<string | null>(null);
  const [draft, setDraft] = useState<ReportDraft>({
    entityType: null,
    entityName: "",
    corridorId: defaults.corridorId,
    hostCountry: defaults.hostCountry,
    description: "",
    language: defaults.language,
    files: [],
  });
  const step = STEPS[stepIndex];
  const isEmployer = draft.entityType === "employer";
  const shownKey = problemKey ?? errorKey;

  function update(changes: Partial<ReportDraft>) {
    setDraft((current) => ({ ...current, ...changes }));
    setProblemKey(null);
  }

  function goBack() {
    setProblemKey(null);
    setStepIndex((index) => Math.max(0, index - 1));
  }

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    if (pending) {
      return;
    }
    const problem = stepProblem(step, draft);
    if (problem) {
      setProblemKey(problem);
      return;
    }
    if (step !== "review") {
      setStepIndex((index) => index + 1);
      return;
    }
    onSubmit(buildRequest(draft, defaults.language), draft.files);
  }

  return (
    <form onSubmit={handleSubmit} noValidate className="card-surface space-y-6 p-5 md:p-7">
      <div>
        <p className="text-xs font-bold uppercase tracking-wide text-radar-ink">
          {t("radar.report.stepOf", { current: stepIndex + 1, total: STEPS.length })}
        </p>
        <ol className="mt-3 flex items-center gap-2" aria-hidden="true">
          {STEPS.map((name, index) => (
            <li key={name} className="flex flex-1 items-center gap-2 last:flex-none">
              <span
                className={cn(
                  "grid h-8 w-8 shrink-0 place-items-center rounded-full text-xs font-extrabold transition-colors duration-base",
                  index < stepIndex && "bg-safe text-white",
                  index === stepIndex && "bg-radar text-white ring-4 ring-radar/20",
                  index > stepIndex && "bg-muted text-muted-foreground"
                )}
              >
                {index < stepIndex ? "✓" : index + 1}
              </span>
              {index < STEPS.length - 1 && (
                <span
                  className={cn(
                    "h-1 flex-1 rounded-full transition-colors duration-base",
                    index < stepIndex ? "bg-safe" : "bg-muted"
                  )}
                />
              )}
            </li>
          ))}
        </ol>
        <h2 className="mt-4 text-xl font-extrabold tracking-tight">
          {t(`radar.report.steps.${step}`)}
        </h2>
      </div>

      {step === "who" && (
        <>
          <fieldset className="space-y-2">
            <legend className="mb-2 text-sm font-bold">{t("radar.report.who.typeLabel")}</legend>
            {ENTITY_TYPES.map((type) => (
              <label
                key={type}
                className={cn(
                  "flex cursor-pointer items-start gap-3 rounded-xl border p-3.5 transition-colors has-[:focus-visible]:ring-2 has-[:focus-visible]:ring-ring",
                  draft.entityType === type
                    ? "border-radar bg-radar-tint"
                    : "bg-card hover:bg-accent"
                )}
              >
                <input
                  type="radio"
                  name="entity-type"
                  value={type}
                  checked={draft.entityType === type}
                  onChange={() => update({ entityType: type })}
                  className="mt-1"
                />
                <span>
                  <span className="block text-sm font-bold">
                    {t(`radar.report.who.types.${type}`)}
                  </span>
                  <span className="block text-xs text-muted-foreground">
                    {t(`radar.report.who.hints.${type}`)}
                  </span>
                </span>
              </label>
            ))}
          </fieldset>

          <div className="space-y-1.5">
            <label htmlFor="radar-entity-name" className="text-sm font-bold">
              {t("radar.report.who.nameLabel")}
            </label>
            <input
              id="radar-entity-name"
              type="text"
              value={draft.entityName}
              maxLength={MAX_NAME_CHARS}
              onChange={(event) => update({ entityName: event.target.value })}
              aria-describedby="radar-entity-name-hint"
              className={fieldClass}
            />
            <p id="radar-entity-name-hint" className="text-xs text-muted-foreground">
              {t("radar.report.who.nameHint")}
            </p>
          </div>
        </>
      )}

      {step === "where" && (
        <div className="space-y-1.5">
          <label htmlFor="radar-location" className="text-sm font-bold">
            {isEmployer ? t("radar.report.where.hostLabel") : t("radar.report.where.corridorLabel")}
          </label>
          {isEmployer ? (
            <select
              id="radar-location"
              value={draft.hostCountry ?? ""}
              onChange={(event) =>
                update({ hostCountry: (event.target.value || null) as HostCountry | null })
              }
              className={fieldClass}
            >
              <option value="">{t("radar.report.where.choose")}</option>
              {HOST_COUNTRIES.map((code) => (
                <option key={code} value={code}>
                  {countryName(code, uiLanguage)}
                </option>
              ))}
            </select>
          ) : (
            <select
              id="radar-location"
              value={draft.corridorId ?? ""}
              onChange={(event) =>
                update({ corridorId: (event.target.value || null) as CorridorId | null })
              }
              className={fieldClass}
            >
              <option value="">{t("radar.report.where.choose")}</option>
              {CORRIDOR_IDS.map((id) => {
                const [from, to] = id.split("-");
                return (
                  <option key={id} value={id}>
                    {countryName(from, uiLanguage)} → {countryName(to, uiLanguage)}
                  </option>
                );
              })}
            </select>
          )}
        </div>
      )}

      {step === "what" && (
        <>
          <div className="space-y-1.5">
            <label htmlFor="radar-description" className="text-sm font-bold">
              {t("radar.report.what.label")}
            </label>
            <textarea
              id="radar-description"
              value={draft.description}
              maxLength={MAX_DESCRIPTION_CHARS}
              rows={7}
              onChange={(event) => update({ description: event.target.value })}
              aria-describedby="radar-description-hint"
              className={cn(fieldClass, "h-auto py-2")}
            />
            <div className="flex justify-between gap-3 text-xs text-muted-foreground">
              <p id="radar-description-hint">{t("radar.report.what.hint")}</p>
              <p className="shrink-0">
                {draft.description.length} / {MAX_DESCRIPTION_CHARS}
              </p>
            </div>
          </div>

          <div className="space-y-1.5">
            <label htmlFor="radar-language" className="text-sm font-bold">
              {t("radar.report.what.languageLabel")}
            </label>
            <select
              id="radar-language"
              value={draft.language ?? defaults.language}
              onChange={(event) => update({ language: event.target.value as LanguageCode })}
              className={fieldClass}
            >
              {SUPPORTED_LANGUAGES.map(({ code, nativeName }) => (
                <option key={code} value={code}>
                  {nativeName}
                </option>
              ))}
            </select>
          </div>
        </>
      )}

      {step === "review" && (
        <>
          <dl className="space-y-3 rounded-xl border bg-radar-tint p-4 text-sm">
            <div>
              <dt className="text-xs text-muted-foreground">{t("radar.report.review.about")}</dt>
              <dd className="font-medium">
                {draft.entityName.trim()}
                {draft.entityType && ` · ${t(`radar.report.who.types.${draft.entityType}`)}`}
              </dd>
            </div>
            <div>
              <dt className="text-xs text-muted-foreground">{t("radar.report.review.where")}</dt>
              <dd>
                {isEmployer
                  ? draft.hostCountry && countryName(draft.hostCountry, uiLanguage)
                  : draft.corridorId}
              </dd>
            </div>
            <div>
              <dt className="text-xs text-muted-foreground">{t("radar.report.review.what")}</dt>
              <dd className="whitespace-pre-wrap break-words">{draft.description.trim()}</dd>
            </div>
          </dl>

          <div className="space-y-2">
            <p className="text-sm font-bold">{t("radar.report.evidence.label")}</p>
            <EvidencePicker
              files={draft.files}
              onChange={(files) => update({ files })}
              disabled={pending}
            />
          </div>
          <p className="text-xs text-muted-foreground">{t("radar.report.privacy")}</p>
        </>
      )}

      {shownKey && (
        <p role="alert" className="text-sm font-medium text-danger-ink">
          {t(shownKey, { min: MIN_DESCRIPTION_CHARS })}
        </p>
      )}

      <div className="flex gap-3">
        {stepIndex > 0 && (
          <Button
            type="button"
            variant="outline"
            className="h-12 flex-1 rounded-xl font-bold"
            onClick={goBack}
            disabled={pending}
          >
            {t("radar.report.back")}
          </Button>
        )}
        <Button
          type="submit"
          size="lg"
          className="h-12 flex-1 rounded-xl bg-radar-deep font-bold text-white hover:bg-radar-deep/90"
          disabled={pending}
        >
          {step !== "review"
            ? t("radar.report.next")
            : pending
              ? t("radar.report.submitting")
              : t("radar.report.submit")}
        </Button>
      </div>
    </form>
  );
}
