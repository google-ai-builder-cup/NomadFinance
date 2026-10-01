import ActivityLogger from "@/components/fib/ActivityLogger";
import { useI18n } from "@/hooks/useI18n";

export default function FIBLogActivity() {
  const { t } = useI18n();

  return (
    <div className="mx-auto max-w-lg space-y-6">
      <header className="space-y-1">
        <h1 className="text-2xl font-bold tracking-tight">{t("fib.log.title")}</h1>
        <p className="text-sm text-muted-foreground">{t("fib.log.subtitle")}</p>
      </header>
      <ActivityLogger />
    </div>
  );
}
