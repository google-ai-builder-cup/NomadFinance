# UI kit: shared components for the Future Scope screens

Seven reusable components (NF-F0-012) for the Coach and Scam Analyzer screens: `ChatBubble`, `QuickReplyChips`, `RiskMeter`, `RiskBadge`, `StepProgress`, `TimelineItem`, `EmptyState`. They live in `frontend/src/components/common/` and follow `docs/design-system.md` (tokens, risk scale, motion rules).

## Rules every component follows

| Rule | What it means in code |
|---|---|
| **No text of its own** | Every visible word and every accessible name arrives as a prop, already translated. The component has no `t()` call and no language file, so the screen that uses it owns the translation keys (`coach.*`, `scam.*`). |
| **Colour is never the only signal** | A state is shown by an icon and by words as well as by colour (`RiskBadge`, `RiskMeter`, `StepProgress`, `TimelineItem`). |
| **Tokens, not hex** | Only Tailwind names backed by `tokens.css` (`bg-primary`, `bg-safe`, `text-muted-foreground`), so the dark theme works with no extra code. |
| **Right-to-left safe** | Logical classes only: `ms-`, `me-`, `ps-`, `pe-`, `start-`, `text-start`, `rounded-es-`, and flex `justify-start` / `justify-end`. The tests fail on `ml-`, `mr-`, `pl-`, `pr-`, `text-left`, `text-right`. None of the six app languages is right-to-left today; this keeps the door open without a rewrite. |
| **Mobile first** | Layouts start at 360 px. Tap targets are at least 44 px (`min-h-11`). |
| **Keyboard and screen reader** | Real `button`, `ol`, `li` and `nav` elements first; ARIA only where HTML has no element for it (`role="meter"`, `aria-current`). Decorative icons carry `aria-hidden`. |

The tests are in the same folder, next to each component (`*.test.tsx`, React Testing Library with `jsdom`). A test file opts in to the browser-like environment with `// @vitest-environment jsdom` on its first line.

---

## `ChatBubble`

One chat message. It has no live-region role of its own: the list that holds the bubbles is the `role="log"`, so a streamed reply is announced once.

| Prop | Type | Notes |
|---|---|---|
| `role` | `"assistant"` \| `"user"` | Assistant at the start of the line, user at the end |
| `children` | node | The message text |
| `streaming` | boolean | Caret after the text; three dots while there is no text yet. Sets `aria-busy` |
| `typingLabel` | string | Spoken while streaming, e.g. "The coach is typing" |
| `speakerLabel` | string | Spoken before the text, e.g. "You said:" |
| `timeLabel` | string | Already formatted |
| `failed`, `failedLabel`, `retryLabel`, `onRetry` | | Shows the failure text and a retry button (only when all three of `failed`, `retryLabel`, `onRetry` are given) |

```tsx
const { t } = useI18n();

<div role="log" aria-live="polite" aria-label={t("coach.chat.log")} className="flex flex-col gap-3">
  {messages.map((m) => (
    <ChatBubble
      key={m.id}
      role={m.role}
      streaming={m.streaming}
      typingLabel={t("coach.chat.typing")}
      speakerLabel={m.role === "user" ? t("coach.chat.you") : t("coach.chat.coach")}
      failed={m.failed}
      failedLabel={t("coach.chat.notSent")}
      retryLabel={t("common.retry")}
      onRetry={() => resend(m.id)}
    >
      {m.text}
    </ChatBubble>
  ))}
</div>
```

For a streamed reply to be read out once, render the text into the bubble while `streaming` is `true` and flip it to `false` when the stream ends. The log announces added content; keep `aria-busy` on the bubble until then.

## `QuickReplyChips`

Suggested answers under a message. Plain buttons: Tab moves between chips, Enter and Space choose.

| Prop | Type | Notes |
|---|---|---|
| `options` | `{ id, label }[]` | `label` already translated |
| `onSelect` | `(option) => void` | |
| `groupLabel` | string | Accessible name, e.g. "Suggested answers" |
| `selectedId` | string \| null | Set to track a choice (`aria-pressed`). Leave it out for one-shot replies |
| `disabled` | boolean | While a reply is being sent |

```tsx
<QuickReplyChips
  groupLabel={t("coach.chat.suggestions")}
  options={HOST_COUNTRIES.map((c) => ({ id: c, label: countryName(c, language) }))}
  disabled={sending}
  onSelect={(option) => send(option.label)}
/>
```

## `RiskMeter`

Three segments for a low, medium or high verdict, always next to a badge with an icon and the level in words. The segments are decorative; the `meter` role carries the value (1 to 3, with `aria-valuetext` set to the visible label).

| Prop | Type | Notes |
|---|---|---|
| `severity` | `"low"` \| `"medium"` \| `"high"` | The scam verdict's `risk_level` |
| `label` | string | Visible level text, e.g. "High risk" |
| `meterLabel` | string | What is measured, as the accessible name, e.g. "Scam risk" |

```tsx
<RiskMeter
  severity={verdict.risk_level}
  label={t(`scam.risk.${verdict.risk_level}`)}
  meterLabel={t("scam.risk.meter")}
/>
```

Not the same as `RiskGauge` (the 0 to 100 contract-health semicircle in `components/visual/`). Use `RiskMeter` for a three-level verdict and `RiskGauge` for a score.

## `RiskBadge`

Already in the app (NF-P1-024), used for contract health, radar risk, alerts and provider flags. Four levels, always an icon next to the words. For a low, medium or high verdict, get the level from `riskLevelForSeverity` in `utils/risk.ts` so a badge and a `RiskMeter` never disagree.

```tsx
<RiskBadge level={riskLevelForSeverity(check.verdict.risk_level)}>
  {t(`scam.risk.${check.verdict.risk_level}`)}
</RiskBadge>
```

## `StepProgress`

A row of numbered steps for a multi-step flow, such as the Coach interview stages. Step names are drawn under the markers from the `sm` breakpoint (640 px) up. On a narrow screen they are visually hidden but still read by a screen reader, and `progressLabel` below the row names the current step. The names sit outside the row's flow, so a long one never squeezes the line between markers.

| Prop | Type | Notes |
|---|---|---|
| `steps` | `{ id, label }[]` | |
| `currentIndex` | number | Zero-based. Steps before it are done |
| `listLabel` | string | Accessible name of the navigation, e.g. "Interview progress" |
| `progressLabel` | string | Visible and spoken position, e.g. "Step 3 of 7: Income". Built by the caller so each language can order the words its own way |
| `statusLabels` | `{ done, current, upcoming }` | Spoken after each step's name |

```tsx
<StepProgress
  steps={STAGES.map((id) => ({ id, label: t(`coach.stage.${id}`) }))}
  currentIndex={STAGES.indexOf(session.stage)}
  listLabel={t("coach.stage.listLabel")}
  progressLabel={t("coach.stage.position", { current: index + 1, total: STAGES.length, name })}
  statusLabels={{
    done: t("coach.stage.done"),
    current: t("coach.stage.current"),
    upcoming: t("coach.stage.upcoming"),
  }}
/>
```

## `TimelineItem`

One entry of a vertical timeline, such as a week of the 90-day plan or a check-in. It is an `li`: put several inside an `ol`. The marker and the line are on the start side, so it mirrors in right-to-left.

| Prop | Type | Notes |
|---|---|---|
| `title` | string | Rendered as an `h3` |
| `children` | node | Description, checklist, links |
| `timeLabel` | string | Already formatted, e.g. "Week 3" |
| `status` | `"done"` \| `"current"` \| `"upcoming"` | Tick, ringed dot, plain dot. `current` sets `aria-current="step"` |
| `statusLabel` | string | Spoken after the title, e.g. "completed" |
| `icon` | Lucide icon | Replaces the default marker |
| `isLast` | boolean | Draws no line below the marker |

```tsx
<ol>
  {plan.weeks.map((week, i) => (
    <TimelineItem
      key={week.number}
      title={week.title}
      timeLabel={t("coach.plan.week", { number: week.number })}
      status={week.done ? "done" : week.number === currentWeek ? "current" : "upcoming"}
      statusLabel={t(`coach.plan.status.${statusOf(week)}`)}
      isLast={i === plan.weeks.length - 1}
    >
      {week.summary}
    </TimelineItem>
  ))}
</ol>
```

The `h3` assumes the timeline sits under an `h2` section heading. If it does not, change the surrounding headings, not the component.

## `EmptyState`

A friendly "nothing here yet" block (NF-P1-026), already used on several pages. NF-F0-012 added `headingLevel` so a screen keeps its heading order.

| Prop | Type | Notes |
|---|---|---|
| `icon` | Lucide icon | Shown in a tile unless `illustration` is set |
| `title`, `description` | string | |
| `action` | node | Usually a button or link |
| `illustration` | node | Replaces the icon tile |
| `headingLevel` | `2` \| `3` \| `4` | Defaults to `2` |

```tsx
<EmptyState
  icon={ShieldQuestion}
  title={t("scam.history.empty.title")}
  description={t("scam.history.empty.description")}
  headingLevel={3}
  action={<Button asChild><Link to="/scam-check">{t("scam.history.empty.cta")}</Link></Button>}
/>
```

---

## What was verified, and how

| Property | How it was checked |
|---|---|
| Behaviour, roles, labels | The tests in `components/common/*.test.tsx` (React Testing Library, user events for click, Tab, Enter and Space) |
| No physical left or right classes | A test on each component's rendered markup |
| 360 px, dark theme, right-to-left | Looked at in the browser preview with a temporary page, in light and dark and with `dir="rtl"`; the page was removed afterwards (see the runbook) |
| Keyboard order and screen-reader names | The test queries use `getByRole(..., { name })`, which is how a screen reader finds them; focus order was tried by hand with Tab in the preview |

A real screen reader (VoiceOver, TalkBack) was **not** run. Each Future Scope screen's accessibility pass (NF-SA-019, NF-FC-023) re-checks the finished pages with `axe` and a screen reader.
