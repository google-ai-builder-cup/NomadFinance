import LoadingSpinner from "@/components/common/LoadingSpinner";
import DeleteAccount from "@/components/profile/DeleteAccount";
import DetailsForm from "@/components/profile/DetailsForm";
import NotificationsForm from "@/components/profile/NotificationsForm";
import { sectionClass } from "@/components/profile/styles";
import { Button } from "@/components/ui/button";
import { useAuth } from "@/hooks/useAuth";
import { useI18n } from "@/hooks/useI18n";
import { useUserProfile } from "@/hooks/useUser";

export default function Profile() {
  const { t } = useI18n();
  const { user } = useAuth();
  const profile = useUserProfile();
  // Phone-only accounts have no name or email, so the number is the only identifier.
  const identity = user?.displayName ?? user?.email ?? user?.phoneNumber ?? "";

  if (profile.isPending) {
    return <LoadingSpinner label={t("common.loading")} className="py-16" />;
  }
  if (profile.isError || profile.data === null) {
    return (
      <div role="alert" className="flex flex-col items-center gap-4 py-16 text-center">
        <p className="text-sm text-muted-foreground">{t("profile.loadError")}</p>
        <Button onClick={() => void profile.refetch()}>{t("common.retry")}</Button>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-2xl space-y-6">
      <header className="space-y-1">
        <h1 className="text-2xl font-bold tracking-tight">{t("profile.title")}</h1>
        <p className="text-sm text-muted-foreground">{t("profile.subtitle")}</p>
      </header>

      <section className={sectionClass} aria-labelledby="account-heading">
        <h2 id="account-heading" className="text-lg font-semibold">
          {t("profile.account.heading")}
        </h2>
        <p className="break-words text-base font-medium">{identity}</p>
        <p className="text-sm text-muted-foreground">{t("profile.account.note")}</p>
      </section>

      <DetailsForm profile={profile.data} />
      <NotificationsForm profile={profile.data} />
      <DeleteAccount />
    </div>
  );
}
