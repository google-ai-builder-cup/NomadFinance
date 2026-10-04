import { TriangleAlert } from "lucide-react";

import EmptyState from "@/components/common/EmptyState";
import { Button } from "@/components/ui/button";
import { useI18n } from "@/hooks/useI18n";

export interface ErrorFallbackProps {
  onRetry: () => void;
  /** Fill the viewport: used when no app shell (header, navigation) is left around it. */
  fullScreen?: boolean;
}

/** The screen people see instead of a crashed page. */
export default function ErrorFallback({ onRetry, fullScreen = false }: ErrorFallbackProps) {
  const { t } = useI18n();

  const content = (
    <EmptyState
      icon={TriangleAlert}
      title={t("errors.boundaryTitle")}
      description={t("errors.boundaryDescription")}
      action={
        <div className="flex flex-wrap justify-center gap-2">
          <Button onClick={onRetry}>{t("common.retry")}</Button>
          {/* A plain link, not <Link>: the root boundary also renders outside the router. */}
          <Button variant="outline" asChild>
            <a href="/dashboard">{t("errors.goHome")}</a>
          </Button>
        </div>
      }
    />
  );

  if (!fullScreen) {
    return <div role="alert">{content}</div>;
  }
  return (
    <main
      role="alert"
      className="mx-auto flex min-h-screen min-h-dvh w-full max-w-md flex-col justify-center px-4 py-10"
    >
      {content}
    </main>
  );
}
