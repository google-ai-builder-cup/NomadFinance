import { ChevronDown, LogOut, UserRound } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import { useAuth } from "@/hooks/useAuth";
import { useI18n } from "@/hooks/useI18n";
import { signOut } from "@/services/authService";
import { initialsOf } from "@/utils/initials";

/** The avatar button and its menu: Profile and Sign out, instead of two loose icons. Closes on
 * Escape, on an outside click and when focus leaves it. */
export default function AccountMenu() {
  const { user } = useAuth();
  const { t } = useI18n();
  const navigate = useNavigate();
  const [open, setOpen] = useState(false);
  const rootRef = useRef<HTMLDivElement>(null);

  // Phone-only accounts have no name or email, so the number is the only identifier.
  const identity = user?.displayName ?? user?.email ?? user?.phoneNumber ?? "";
  const shortName = user?.displayName?.split(" ")[0] ?? "";

  useEffect(() => {
    if (!open) {
      return undefined;
    }
    const onPointer = (event: PointerEvent) => {
      if (!rootRef.current?.contains(event.target as Node)) {
        setOpen(false);
      }
    };
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        setOpen(false);
        rootRef.current?.querySelector("button")?.focus();
      }
    };
    document.addEventListener("pointerdown", onPointer);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("pointerdown", onPointer);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  // ProtectedRoute also sends a signed-out visitor to "/", so this is only a direct route there.
  async function handleSignOut() {
    setOpen(false);
    await signOut();
    navigate("/", { replace: true });
  }

  const itemClass =
    "flex min-h-11 w-full items-center gap-3 rounded-lg px-3 text-left text-sm font-medium hover:bg-accent focus-visible:bg-accent";

  return (
    <div ref={rootRef} className="relative">
      <button
        type="button"
        aria-haspopup="menu"
        aria-expanded={open}
        aria-label={t("layout.accountMenu")}
        onClick={() => setOpen((v) => !v)}
        className="flex h-11 items-center gap-2 rounded-full border bg-card py-1 pl-1 pr-2 shadow-sm transition-colors hover:bg-accent sm:h-10"
      >
        <span className="flex h-8 w-8 items-center justify-center rounded-full bg-primary text-xs font-bold text-primary-foreground">
          {initialsOf(identity)}
        </span>
        {shortName && (
          <span className="hidden max-w-[7rem] truncate text-sm font-semibold lg:inline">
            {shortName}
          </span>
        )}
        <ChevronDown className="h-4 w-4 text-muted-foreground" aria-hidden="true" />
      </button>
      {open && (
        <div
          role="menu"
          aria-label={t("layout.accountMenu")}
          className="glass absolute right-0 top-full z-50 mt-2 w-60 rounded-xl border p-1.5 shadow-lg animate-fade-up"
        >
          {identity && (
            <p className="truncate px-3 py-2 text-xs text-muted-foreground" title={identity}>
              {identity}
            </p>
          )}
          <Link role="menuitem" to="/profile" className={itemClass} onClick={() => setOpen(false)}>
            <UserRound className="h-4 w-4" aria-hidden="true" />
            {t("nav.profile")}
          </Link>
          <button
            type="button"
            role="menuitem"
            className={itemClass}
            onClick={() => void handleSignOut()}
          >
            <LogOut className="h-4 w-4" aria-hidden="true" />
            {t("auth.signOut")}
          </button>
        </div>
      )}
    </div>
  );
}
