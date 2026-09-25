import { type FormEvent, useState } from "react";

import { fieldClass, sectionClass } from "@/components/profile/styles";
import SaveStatus from "@/components/profile/SaveStatus";
import { Button } from "@/components/ui/button";
import { useI18n } from "@/hooks/useI18n";
import { useUpdateProfile } from "@/hooks/useUser";
import i18n from "@/lib/i18n";
import { clearSessionLanguage, SUPPORTED_LANGUAGES } from "@/lib/languages";
import {
  HOME_COUNTRIES,
  type HomeCountry,
  HOST_COUNTRIES,
  type HostCountry,
  JOB_TYPES,
  type JobType,
  type LanguageCode,
} from "@/types/enums";
import type { ProfileChanges, UserProfile } from "@/types/user";
import { countryName } from "@/utils/format";

interface Draft {
  preferred_language: LanguageCode;
  host_country: HostCountry;
  home_country: HomeCountry;
  job_type: JobType;
}

/** What Firestore holds. Onboarding guarantees the fields; the fallbacks only satisfy the types. */
function savedValues(profile: UserProfile): Draft {
  return {
    preferred_language: profile.preferred_language ?? "en",
    host_country: profile.host_country ?? HOST_COUNTRIES[0],
    home_country: profile.home_country ?? HOME_COUNTRIES[0],
    job_type: profile.job_type ?? "other",
  };
}

/** Only the fields that differ, so a save never rewrites what was not touched. */
function changesBetween(saved: Draft, draft: Draft): ProfileChanges {
  const changes: ProfileChanges = {};
  if (draft.preferred_language !== saved.preferred_language) {
    changes.preferred_language = draft.preferred_language;
  }
  if (draft.host_country !== saved.host_country) {
    changes.host_country = draft.host_country;
  }
  if (draft.home_country !== saved.home_country) {
    changes.home_country = draft.home_country;
  }
  if (draft.job_type !== saved.job_type) {
    changes.job_type = draft.job_type;
  }
  return changes;
}

export interface DetailsFormProps {
  profile: UserProfile;
}

export default function DetailsForm({ profile }: DetailsFormProps) {
  const { t } = useI18n();
  const save = useUpdateProfile();
  const saved = savedValues(profile);
  const [draft, setDraft] = useState<Draft>(saved);
  const language = i18n.resolvedLanguage ?? "en";

  const changes = changesBetween(saved, draft);
  const dirty = Object.keys(changes).length > 0;

  function edit<K extends keyof Draft>(field: K, value: string) {
    // The options come from the enum lists, so the value is always one of them.
    setDraft((previous) => ({ ...previous, [field]: value as Draft[K] }));
  }

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    if (!dirty) {
      return;
    }
    save.mutate(changes, {
      onSuccess: () => {
        if (changes.preferred_language !== undefined) {
          // A header quick-switch would otherwise keep overriding the saved language.
          clearSessionLanguage();
          void i18n.changeLanguage(changes.preferred_language);
        }
      },
    });
  }

  return (
    <form onSubmit={handleSubmit} className={sectionClass} aria-labelledby="details-heading">
      <h2 id="details-heading" className="text-lg font-semibold">
        {t("profile.details.heading")}
      </h2>

      <div className="space-y-1.5">
        <label htmlFor="profile-language" className="text-sm font-medium">
          {t("profile.details.language")}
        </label>
        <select
          id="profile-language"
          value={draft.preferred_language}
          onChange={(event) => edit("preferred_language", event.target.value)}
          aria-describedby="profile-language-hint"
          disabled={save.isPending}
          className={fieldClass}
        >
          {SUPPORTED_LANGUAGES.map(({ code, nativeName }) => (
            <option key={code} value={code}>
              {nativeName}
            </option>
          ))}
        </select>
        <p id="profile-language-hint" className="text-xs text-muted-foreground">
          {t("profile.details.languageHint")}
        </p>
      </div>

      <div className="space-y-1.5">
        <label htmlFor="profile-host" className="text-sm font-medium">
          {t("profile.details.hostCountry")}
        </label>
        <select
          id="profile-host"
          value={draft.host_country}
          onChange={(event) => edit("host_country", event.target.value)}
          aria-describedby="profile-host-hint"
          disabled={save.isPending}
          className={fieldClass}
        >
          {HOST_COUNTRIES.map((code) => (
            <option key={code} value={code}>
              {countryName(code, language)}
            </option>
          ))}
        </select>
        <p id="profile-host-hint" className="text-xs text-muted-foreground">
          {t("profile.details.hostCountryHint")}
        </p>
      </div>

      <div className="space-y-1.5">
        <label htmlFor="profile-home" className="text-sm font-medium">
          {t("profile.details.homeCountry")}
        </label>
        <select
          id="profile-home"
          value={draft.home_country}
          onChange={(event) => edit("home_country", event.target.value)}
          disabled={save.isPending}
          className={fieldClass}
        >
          {HOME_COUNTRIES.map((code) => (
            <option key={code} value={code}>
              {countryName(code, language)}
            </option>
          ))}
        </select>
      </div>

      <div className="space-y-1.5">
        <label htmlFor="profile-job" className="text-sm font-medium">
          {t("profile.details.jobType")}
        </label>
        <select
          id="profile-job"
          value={draft.job_type}
          onChange={(event) => edit("job_type", event.target.value)}
          disabled={save.isPending}
          className={fieldClass}
        >
          {JOB_TYPES.map((id) => (
            <option key={id} value={id}>
              {t(`onboarding.jobTypes.${id}`)}
            </option>
          ))}
        </select>
      </div>

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
