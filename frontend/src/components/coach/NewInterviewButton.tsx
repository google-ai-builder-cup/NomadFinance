import { RotateCcw } from "lucide-react";

import { Button } from "@/components/ui/button";
import { useFocusOnMount } from "@/hooks/useFocusOnMount";
import { useI18n } from "@/hooks/useI18n";
import { cn } from "@/lib/utils";

export interface NewInterviewButtonProps {
  onClick: () => void;
  /** Take focus when it appears: the worker backed out of the question that replaced it. */
  focusOnMount?: boolean;
  className?: string;
}

/** The way to start over, at any point of the interview and after it. */
export default function NewInterviewButton({
  onClick,
  focusOnMount = false,
  className,
}: NewInterviewButtonProps) {
  const { t } = useI18n("coach");
  const ref = useFocusOnMount<HTMLButtonElement>(focusOnMount);
  return (
    <Button
      ref={ref}
      type="button"
      variant="outline"
      size="sm"
      className={cn("min-h-11 shrink-0 gap-2 font-bold", className)}
      onClick={onClick}
    >
      <RotateCcw className="h-4 w-4" aria-hidden="true" />
      {t("chat.newInterview")}
    </Button>
  );
}

export interface NewInterviewConfirmProps {
  /** Close this interview and start a new one. */
  onRestart: () => void;
  onCancel: () => void;
  restarting?: boolean;
  className?: string;
}

/** The question the button asks first: the answers go with the old interview, and a plan that was
 * already made is not touched. */
export function NewInterviewConfirm({
  onRestart,
  onCancel,
  restarting = false,
  className,
}: NewInterviewConfirmProps) {
  const { t } = useI18n("coach");
  const question = useFocusOnMount<HTMLParagraphElement>();
  return (
    <div
      role="group"
      aria-label={t("chat.newInterview")}
      className={cn("w-full space-y-2 rounded-2xl border bg-card p-3", className)}
    >
      <p ref={question} tabIndex={-1} className="text-sm font-semibold focus:outline-none">
        {t("resume.confirm")}
      </p>
      <div className="flex flex-wrap gap-2">
        <Button
          type="button"
          size="sm"
          className="min-h-11"
          disabled={restarting}
          onClick={onRestart}
        >
          {t("resume.confirmYes")}
        </Button>
        <Button
          type="button"
          size="sm"
          variant="outline"
          className="min-h-11"
          disabled={restarting}
          onClick={onCancel}
        >
          {t("resume.confirmNo")}
        </Button>
      </div>
    </div>
  );
}
