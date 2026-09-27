import { LogOut, UserRound } from "lucide-react";
import { Link, useNavigate } from "react-router-dom";

import LanguageSelector from "@/components/layout/LanguageSelector";
import { Button } from "@/components/ui/button";
import { useAuth } from "@/hooks/useAuth";
import { useI18n } from "@/hooks/useI18n";
import { signOut } from "@/services/authService";

export default function Header() {
  const { user } = useAuth();
  const { t } = useI18n();
  const navigate = useNavigate();

  // Without this, ProtectedRoute would catch the signed-out state and redirect to /sign-in
  // instead of the public landing page.
  async function handleSignOut() {
    await signOut();
    navigate("/", { replace: true });
  }
  // Phone-only accounts have no name or email, so the number is the only identifier.
  const identity = user?.displayName ?? user?.email ?? user?.phoneNumber ?? "";

  return (
    <header className="sticky top-0 z-40 border-b bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/80">
      <div className="flex h-14 items-center justify-between gap-3 px-4 md:px-8">
        <Link
          to="/dashboard"
          className="rounded-md text-lg font-bold tracking-tight focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
        >
          NomadFinance
        </Link>
        <div className="flex min-w-0 items-center gap-2">
          <span
            className="hidden max-w-[16rem] truncate text-sm text-muted-foreground sm:inline"
            title={identity}
          >
            {identity}
          </span>
          <LanguageSelector />
          <Button variant="ghost" size="icon" asChild>
            <Link to="/profile" aria-label={t("nav.profile")} title={t("nav.profile")}>
              <UserRound className="h-4 w-4" aria-hidden="true" />
            </Link>
          </Button>
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
      </div>
    </header>
  );
}
