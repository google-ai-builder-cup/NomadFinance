import { LogOut } from "lucide-react";

import { Button } from "@/components/ui/button";
import { useAuth } from "@/hooks/useAuth";
import { useI18n } from "@/hooks/useI18n";
import { signOut } from "@/services/authService";

// Placeholder behind ProtectedRoute so sign-in can be tested end to end (NF-P1-009).
// Replaced by the real dashboard with the 4 pillar cards in NF-P1-010.
export default function Dashboard() {
  const { user } = useAuth();
  const { t } = useI18n();
  const name = user?.displayName ?? user?.email ?? user?.phoneNumber ?? "";

  return (
    <main className="mx-auto flex min-h-screen max-w-md flex-col justify-center gap-4 px-4">
      <h1 className="text-2xl font-bold tracking-tight">{t("dashboard.placeholder.title")}</h1>
      <p className="text-muted-foreground">{t("dashboard.placeholder.signedInAs", { name })}</p>
      <Button variant="outline" className="w-full" onClick={() => void signOut()}>
        <LogOut className="mr-2 h-4 w-4" aria-hidden="true" />
        {t("auth.signOut")}
      </Button>
    </main>
  );
}
