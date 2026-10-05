import { useI18n } from "@/hooks/useI18n";

export default function Footer() {
  const { t } = useI18n();

  return (
    <footer className="border-t px-4 py-6 text-center text-xs text-muted-foreground md:px-8">
      <p className="font-medium">{t("layout.footer.tagline")}</p>
      <p className="mt-1">{t("layout.footer.disclaimer")}</p>
      <p className="mt-1">{t("layout.footer.rights", { year: new Date().getFullYear() })}</p>
    </footer>
  );
}
