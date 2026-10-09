import StepProgress from "@/components/common/StepProgress";
import { useI18n } from "@/hooks/useI18n";
import type { CoachStage } from "@/types/coach";

// `plan` is not a step of the interview: once the answers are confirmed, every step is done.
const STEPS = ["intro", "income", "obligations", "debt", "savings", "review"] as const;

export interface StageStepperProps {
  stage: CoachStage;
}

/** Where the interview stands, as the shared step row (NF-F0-012). */
export default function StageStepper({ stage }: StageStepperProps) {
  const { t } = useI18n("coach");
  const index = stage === "plan" ? STEPS.length : STEPS.indexOf(stage);
  const position =
    index < STEPS.length
      ? t("stage.position", {
          current: index + 1,
          total: STEPS.length,
          name: t(`stage.${STEPS[index]}`),
        })
      : t("stage.complete");

  return (
    <StepProgress
      steps={STEPS.map((id) => ({ id, label: t(`stage.${id}`) }))}
      currentIndex={index}
      listLabel={t("stage.listLabel")}
      progressLabel={position}
      statusLabels={{
        done: t("stage.done"),
        current: t("stage.current"),
        upcoming: t("stage.upcoming"),
      }}
    />
  );
}
