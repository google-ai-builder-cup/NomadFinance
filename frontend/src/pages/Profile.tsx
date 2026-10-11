import LoadingSpinner from "@/components/common/LoadingSpinner";
import DeleteAccount from "@/components/profile/DeleteAccount";
import DetailsForm from "@/components/profile/DetailsForm";
import NotificationsForm from "@/components/profile/NotificationsForm";
import { sectionClass } from "@/components/profile/styles";
import { Button } from "@/components/ui/button";
import { useAuth } from "@/hooks/useAuth";
import { useI18n } from "@/hooks/useI18n";
import { useUserProfile } from "@/hooks/useUser";
import { initialsOf } from "@/utils/initials";

export default function Profile() {
  const { t } = useI18n();
  const { user } = useAuth();
  const profile = useUserProfile();
  // Phone-only accounts have no name or email, so the number is the only identifier.
  const identity = user?.displayName ?? user?.email ?? user?.phoneNumber ?? "";

  if (profile.isPending) {
    return (
      <div className="space-y-5">
        <h1 className="text-2xl font-extrabold tracking-tight md:text-3xl">{t("profile.title")}</h1>
        <LoadingSpinner label={t("common.loading")} className="py-16" />
      </div>
    );
  }
  if (profile.isError || profile.data === null) {
    return (
      <div className="space-y-5">
        <h1 className="text-2xl font-extrabold tracking-tight md:text-3xl">{t("profile.title")}</h1>
        <div role="alert" className="flex flex-col items-center gap-4 py-16 text-center">
          <p className="text-sm text-muted-foreground">{t("profile.loadError")}</p>
          <Button onClick={() => void profile.refetch()}>{t("common.retry")}</Button>
        </div>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-3xl space-y-5">
      <header className="card-surface card-edge flex flex-wrap items-center gap-4 bg-gradient-to-br from-accent via-card to-card p-5 md:p-7">
        <span className="grid h-16 w-16 shrink-0 place-items-center rounded-full bg-primary text-xl font-extrabold text-primary-foreground shadow-md">
          {initialsOf(identity)}
        </span>
        <div className="min-w-0 space-y-1">
          <h1 className="text-2xl font-extrabold tracking-tight md:text-3xl">
            {t("profile.title")}
          </h1>
          <p className="text-sm text-muted-foreground">{t("profile.subtitle")}</p>
        </div>
      </header>

      <section className={sectionClass} aria-labelledby="account-heading">
        <h2 id="account-heading" className="text-lg font-bold tracking-tight">
          {t("profile.account.heading")}
        </h2>
        <p className="break-words text-base font-semibold">{identity}</p>
        <p className="text-sm text-muted-foreground">{t("profile.account.note")}</p>
      </section>

      <DetailsForm profile={profile.data} />
      <NotificationsForm profile={profile.data} />
      <DeleteAccount />
    </div>
  );
}
