import { ClipboardPaste, ImageIcon, ScanSearch, ShieldCheck } from "lucide-react";
import { type FormEvent, useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { useSearchParams } from "react-router-dom";

import PageHeader from "@/components/common/PageHeader";
import AnalyzingProgress from "@/components/scam/AnalyzingProgress";
import MessageInput from "@/components/scam/MessageInput";
import ScamErrorNotice from "@/components/scam/ScamErrorNotice";
import ScamResult from "@/components/scam/ScamResult";
import ScreenshotPicker from "@/components/scam/ScreenshotPicker";
import { Button } from "@/components/ui/button";
import { useI18n } from "@/hooks/useI18n";
import { useScamAnalyze } from "@/hooks/useScamAnalyze";
import { useUserProfile } from "@/hooks/useUser";
import { cn } from "@/lib/utils";
import { CORRIDOR_IDS, isLanguageCode, type CorridorId } from "@/types/enums";
import type { ScamCheckInput } from "@/types/scam";
import {
  clearSharedMessage,
  isSubmittable,
  messageFromShare,
  peekSharedMessage,
} from "@/utils/scamInput";

type Mode = "text" | "screenshot";

const MODES = [
  { mode: "text", icon: ClipboardPaste, labelKey: "input.modeText" },
  { mode: "screenshot", icon: ImageIcon, labelKey: "input.modeScreenshot" },
] as const;

// Its own chunk, fetched only once the `scam` flag is on for the signed-in user. Pasting, a
// screenshot and a message shared from another app all fill the same form and leave through
// `submit`, so there is one path to the analyzer.
export default function ScamCheckHome() {
  const { t } = useI18n("scam");
  const { i18n } = useTranslation();
  const profile = useUserProfile().data;
  const [params, setParams] = useSearchParams();
  const analyze = useScamAnalyze();

  // The share target opens /scam-check?title=&text=&url=. The message is only put in the box, not
  // sent: a check spends one of the 20 an hour, so the worker looks at it first. A signed-out
  // worker's share was kept for the tab (main.tsx) and is found here after signing in.
  const [arrived] = useState(() => messageFromShare(params) || peekSharedMessage());
  const [mode, setMode] = useState<Mode>("text");
  const [text, setText] = useState(arrived);
  const [file, setFile] = useState<File | null>(null);
  const [shared, setShared] = useState(arrived !== "");

  // The address is cleaned so a reload does not bring the message back.
  useEffect(() => {
    clearSharedMessage();
    if (["title", "text", "url"].some((key) => params.has(key))) {
      setParams({}, { replace: true });
    }
    // Once, on arrival.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const language = isLanguageCode(i18n.resolvedLanguage) ? i18n.resolvedLanguage : "en";
  const ownRoute = `${profile?.host_country ?? ""}-${profile?.home_country ?? ""}`;
  // Sent only when it is one of the six routes: any other value is a 422.
  const corridorId = CORRIDOR_IDS.find((id: CorridorId) => id === ownRoute);

  // The other mode's content stays in its state but is never sent.
  const input: ScamCheckInput | null =
    mode === "text" ? { kind: "text", text } : file ? { kind: "screenshot", file } : null;
  const canSubmit = input !== null && isSubmittable(input) && !analyze.isPending;

  function submit(next: ScamCheckInput) {
    if (isSubmittable(next)) {
      analyze.mutate({ input: next, language, corridorId });
    }
  }

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    if (input !== null) {
      submit(input);
    }
  }

  function startOver() {
    analyze.reset();
    setText("");
    setFile(null);
    setShared(false);
  }

  return (
    <div className="space-y-5">
      <PageHeader
        pillar="radar"
        icon={ScanSearch}
        title={t("home.title")}
        description={t("home.description")}
        compact
      />

      {analyze.isSuccess ? (
        <ScamResult result={analyze.data} onCheckAnother={startOver} />
      ) : analyze.isPending ? (
        <AnalyzingProgress />
      ) : (
        <form onSubmit={handleSubmit} className="space-y-4" noValidate>
          {analyze.isError && (
            <ScamErrorNotice
              error={analyze.error}
              onRetry={() => analyze.variables && analyze.mutate(analyze.variables)}
            />
          )}

          <div role="group" aria-label={t("input.modeLabel")} className="grid grid-cols-2 gap-2">
            {MODES.map(({ mode: value, icon: Icon, labelKey }) => (
              <button
                key={value}
                type="button"
                aria-pressed={mode === value}
                onClick={() => setMode(value)}
                className={cn(
                  "flex min-h-12 items-center justify-center gap-2 rounded-xl border px-3 text-sm font-bold",
                  "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
                  mode === value
                    ? "border-radar bg-radar-tint text-radar-ink"
                    : "border-input bg-card hover:bg-accent"
                )}
              >
                <Icon className="h-4 w-4" aria-hidden="true" />
                {t(labelKey)}
              </button>
            ))}
          </div>

          {mode === "text" ? (
            <>
              {shared && (
                <p role="status" className="rounded-xl bg-radar-tint px-4 py-3 text-sm">
                  {t("input.shared")}
                </p>
              )}
              <MessageInput value={text} onChange={setText} />
            </>
          ) : (
            <ScreenshotPicker file={file} onSelect={setFile} onClear={() => setFile(null)} />
          )}

          <Button type="submit" size="lg" className="w-full" disabled={!canSubmit}>
            {t("input.submit")}
          </Button>

          <p className="flex items-start gap-2 text-xs text-muted-foreground">
            <ShieldCheck className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
            {t("input.privacy")}
          </p>
        </form>
      )}
    </div>
  );
}
