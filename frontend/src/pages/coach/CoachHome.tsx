import { GraduationCap } from "lucide-react";
import { useState } from "react";

import CoachChat from "@/components/coach/CoachChat";
import CoachNotice from "@/components/coach/CoachNotice";
import PlanCard from "@/components/coach/PlanCard";
import LanguageSwitch from "@/components/coach/LanguageSwitch";
import { Skeleton } from "@/components/ui/skeleton";
import { useAuth } from "@/hooks/useAuth";
import { useCoachOverview } from "@/hooks/useCoachPlan";
import { useCoachRestart, useCoachSession } from "@/hooks/useCoachSession";
import { useI18n } from "@/hooks/useI18n";
import { cn } from "@/lib/utils";
import { toFailure } from "@/utils/coachErrors";
import { PILLAR_STYLES } from "@/utils/pillars";

// Its own chunk, fetched only once the `coach` flag is on for the signed-in user. While the
// interview is under way the page is as tall as the screen below the header and above the phone's
// tab bar (64 px + 48 px of padding, and 96 px for the bar on a phone), so the conversation
// scrolls inside it and the page itself does not move while a reply streams in. From the review on
// it is an ordinary page that grows with the table of answers, the score and the conversation.
export default function CoachHome() {
  const { t } = useI18n("coach");
  const { user } = useAuth();
  const session = useCoachSession();
  const restart = useCoachRestart();
  // The way back to a plan that was made; if this read fails the Coach page is as it was.
  const plan = useCoachOverview().data?.plan;
  const [flowing, setFlowing] = useState(false);

  return (
    <div
      className={cn(
        "mx-auto flex w-full max-w-2xl flex-col gap-3",
        !flowing && "min-h-[28rem] h-[calc(100dvh-13rem)] md:h-[calc(100dvh-9rem)]"
      )}
    >
      <header className="flex shrink-0 items-center gap-3">
        <span
          className={cn(
            "flex h-9 w-9 shrink-0 items-center justify-center rounded-xl shadow-sm sm:h-10 sm:w-10",
            PILLAR_STYLES.coach.tile
          )}
        >
          <GraduationCap className="h-5 w-5" aria-hidden="true" />
        </span>
        <div className="min-w-0">
          <h1 className="text-xl font-extrabold tracking-tight">{t("home.title")}</h1>
          {/* Left out on a phone: the room goes to the conversation. */}
          <p className="hidden text-sm text-muted-foreground sm:block">{t("home.description")}</p>
        </div>
        <LanguageSwitch />
      </header>

      {plan && <PlanCard plan={plan} />}

      {session.isPending ? (
        <div role="status" aria-label={t("home.loading")} className="flex flex-1 flex-col gap-3">
          <Skeleton className="h-16 w-full rounded-2xl" />
          <Skeleton className="min-h-0 w-full flex-1 rounded-2xl" />
          <Skeleton className="h-32 w-full rounded-2xl" />
        </div>
      ) : session.isError ? (
        <CoachNotice
          failure={toFailure(session.error)}
          onRetry={() => void session.refetch()}
          onRestart={() => void session.refetch()}
        />
      ) : (
        <CoachChat
          // A new session is a new chat: the reducer starts again from its transcript.
          key={session.data.id}
          session={session.data}
          onRestart={() => restart.mutate()}
          restarting={restart.isPending}
          restartError={restart.isError ? restart.error : undefined}
          onFlowChange={setFlowing}
          uid={user?.uid}
        />
      )}
    </div>
  );
}
