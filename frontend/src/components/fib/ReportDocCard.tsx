import BrandMark from "@/components/visual/BrandMark";
import ScoreRing from "@/components/visual/ScoreRing";
import TiltCard from "@/components/visual/TiltCard";
import { useI18n } from "@/hooks/useI18n";
import { METRIC_KEYS, type FinancialProfile } from "@/types/fib";
import { STATUS_COLOR, STATUS_PAPER_INK, statusFor } from "@/utils/fibScore";

/** A paper-like preview of the exportable PDF, built from the worker's own computed profile: the
 * same score and metrics the report will carry, tilted in 3D so it reads as a document. It is a
 * preview of the figures, not the PDF itself (the full preview opens from the button). */
export default function ReportDocCard({
  profile,
  holderName,
}: {
  profile: FinancialProfile;
  holderName: string;
}) {
  const { t } = useI18n();
  const status = statusFor(profile.overall_score);
  return (
    <div className="grid place-items-center p-2 [perspective:1100px] md:p-6">
      <TiltCard className="w-full max-w-[21rem]">
        <div
          aria-hidden="true"
          className="rounded-md border border-border bg-paper p-6 text-paper-ink shadow-lg [transform:rotateY(-14deg)_rotateX(6deg)_rotate(2deg)] motion-reduce:[transform:none]"
        >
          <div className="flex items-center gap-2 border-b-2 border-identity pb-2.5">
            <BrandMark size={22} />
            <b className="text-xs">{t("fib.export.title")}</b>
          </div>
          <div className="my-4 flex items-center gap-3">
            <ScoreRing
              value={profile.overall_score}
              color={STATUS_COLOR[status]}
              size={64}
              strokeWidth={9}
              label={`${profile.overall_score}`}
            >
              <span className="text-base text-paper-ink">{profile.overall_score}</span>
            </ScoreRing>
            <div className="min-w-0">
              <p className="truncate text-sm font-extrabold">
                {holderName || t("fib.export.holderNamePlaceholder")}
              </p>
              <p className="text-xs font-semibold" style={{ color: STATUS_PAPER_INK[status] }}>
                {t(`fib.score.status.${status}`)}
              </p>
            </div>
          </div>
          <div className="space-y-2.5">
            {METRIC_KEYS.map((key) => {
              const score = profile.metrics[key].score;
              return (
                <div key={key}>
                  <div className="mb-1 flex justify-between text-[10.5px] font-semibold text-paper-muted">
                    <span className="truncate">{t(`fib.score.metrics.${key}`)}</span>
                    <span>{score ?? "—"}</span>
                  </div>
                  <div className="h-1.5 rounded-full bg-paper-muted/20">
                    <div
                      className="h-full rounded-full bg-identity"
                      style={{ width: `${score ?? 0}%` }}
                    />
                  </div>
                </div>
              );
            })}
          </div>
          <div className="mt-5 grid gap-1.5">
            {[90, 78, 56].map((w) => (
              <div key={w} className="h-1.5 rounded bg-paper-muted/20" style={{ width: `${w}%` }} />
            ))}
          </div>
        </div>
      </TiltCard>
    </div>
  );
}
