import { LogOut } from "lucide-react";
import { Link } from "react-router-dom";

import { Button } from "@/components/ui/button";
import { useAuth } from "@/hooks/useAuth";
import { useI18n } from "@/hooks/useI18n";
import { signOut } from "@/services/authService";

export default function Header() {
  const { user } = useAuth();
  const { t } = useI18n();
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
      </div>
    </header>
  );
}
