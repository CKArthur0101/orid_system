"use client";

import { useMemo } from "react";
import { Card, CardContent } from "@/components/ui/card";

export type StageKey = "O" | "R" | "I" | "D";
export type ConditionKey = "genai" | "template";

export type StageDraft = {
  d1: string;
  d2: string;
  // ✅ 新增：存 AI 回饋（不改 DB schema，直接存在 content JSON）
  tips?: {
    d1?: string[];
    d2?: string[];
  };
  done?: boolean;
};

export type OridWritingV1 = {
  schema: "orid_writing_v1";
  week: number;
  stages: Record<StageKey, StageDraft>;
};

const STAGES: { key: StageKey; label: string }[] = [
  { key: "O", label: "O 客觀" },
  { key: "R", label: "R 感受" },
  { key: "I", label: "I 意義" },
  { key: "D", label: "D 行動" },
];

function idxOfStage(s: string) {
  return STAGES.findIndex((x) => x.key === s);
}

export default function WritingPanel(props: {
  data: OridWritingV1;
  setData: (v: OridWritingV1) => void;
  activeStage: StageKey;
  setActiveStage: (s: StageKey) => void;
  currentStageFromChat: string;
  condition: ConditionKey;

  // ✅ 新增：由外層 page.tsx 傳入（因為只有外層知道 sessionId/week）
  onAssist?: (draft: "d1" | "d2", stage: StageKey) => Promise<void>;
  assistLoading?: boolean;
  assistError?: string | null;
}) {
  const {
    data,
    setData,
    activeStage,
    setActiveStage,
    currentStageFromChat,
    condition,
    onAssist,
    assistLoading = false,
    assistError = null,
  } = props;

  const unlockedIndex = useMemo(() => {
    const i = idxOfStage(currentStageFromChat || "O");
    return i < 0 ? 0 : i;
  }, [currentStageFromChat]);

  const activeIndex = idxOfStage(activeStage);
  const locked = activeIndex > unlockedIndex;

  const stage = data.stages[activeStage];

  // ✅ 顯示 AI tips：以 Draft1 的建議為主（因為通常是寫完 D1 → 看建議 → 寫 D2）
  const tipsForD1 = stage.tips?.d1 ?? [];

  const feedbackText = useMemo(() => {
    if (condition === "genai") {
      if (tipsForD1.length) {
        return tipsForD1.map((t) => `• ${t}`).join("\n");
      }
      return [
        "• 你可以按「AI 生成 Draft 1」先出第一版",
        "• 或先自己寫 Draft 1，再按「AI 生成 Draft 2」讓系統示範怎麼修",
      ].join("\n");
    }
    return [
      "• 固定模板檢核（不個人化、不生成改寫）",
      "• 例：至少兩句、需包含「因為」、需連回故事線索、D 段需具體做法",
    ].join("\n");
  }, [condition, tipsForD1]);

  return (
    <div className="space-y-3">
      {/* Tabs */}
      <div className="flex flex-wrap gap-2">
        {STAGES.map((s, i) => {
          const disabled = i > unlockedIndex;
          const isActive = s.key === activeStage;
          return (
            <button
              key={s.key}
              disabled={disabled}
              onClick={() => setActiveStage(s.key)}
              className={[
                "rounded-full border px-3 py-1 text-sm",
                isActive
                  ? "bg-primary text-primary-foreground border-primary"
                  : "bg-muted/30",
                disabled ? "opacity-40 cursor-not-allowed" : "hover:bg-muted",
              ].join(" ")}
              title={disabled ? "請先完成前面對話" : ""}
            >
              {s.label}
            </button>
          );
        })}
      </div>

      {locked && (
        <div className="text-sm text-muted-foreground">
          目前聊天尚未到這一段，請先完成前面對話再寫。
        </div>
      )}

      {/* Draft 1 */}
      <Card>
        <CardContent className="p-4 space-y-2">
          <div className="flex items-center justify-between gap-2">
            <div className="text-[15px] font-medium">Draft 1（第一稿）</div>

            {condition === "genai" && (
              <button
                type="button"
                disabled={locked || assistLoading || !onAssist}
                onClick={() => onAssist?.("d1", activeStage)}
                className="rounded-md border px-3 py-1 text-sm hover:bg-muted disabled:opacity-50"
                title="用聊天紀錄 + 閱讀內容產生本段 Draft 1（示範用）"
              >
                {assistLoading ? "生成中…" : "AI 生成 Draft 1"}
              </button>
            )}
          </div>

          <textarea
            disabled={locked}
            className="min-h-[165px] w-full rounded-md border bg-background p-3 text-[15px] outline-none"
            placeholder="先把這一段用 2–4 句寫清楚"
            value={stage.d1}
            onChange={(e) =>
              setData({
                ...data,
                stages: {
                  ...data.stages,
                  [activeStage]: { ...stage, d1: e.target.value },
                },
              })
            }
          />
        </CardContent>
      </Card>

      {/* Feedback */}
      <Card>
        <CardContent className="p-4 space-y-2">
          <div className="text-[15px] font-medium">回饋提示（兩組差異在這裡）</div>
          <pre className="whitespace-pre-wrap text-sm text-muted-foreground">
            {feedbackText}
          </pre>
          {assistError && (
            <div className="text-sm text-red-600 whitespace-pre-wrap">
              ❌ {assistError}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Draft 2 */}
      <Card>
        <CardContent className="p-4 space-y-2">
          <div className="flex items-center justify-between gap-2">
            <div className="text-[15px] font-medium">Draft 2（修訂稿）</div>

            {condition === "genai" && (
              <button
                type="button"
                disabled={locked || assistLoading || !onAssist || !stage.d1.trim()}
                onClick={() => onAssist?.("d2", activeStage)}
                className="rounded-md border px-3 py-1 text-sm hover:bg-muted disabled:opacity-50"
                title="用 Draft 1 + 建議示範產生修訂稿（示範用）"
              >
                {assistLoading ? "生成中…" : "AI 生成 Draft 2"}
              </button>
            )}
          </div>

          <textarea
            disabled={locked}
            className="min-h-[165px] w-full rounded-md border bg-background p-3 text-[15px] outline-none"
            placeholder="依回饋修訂（可只改 1–2 句也可以）"
            value={stage.d2}
            onChange={(e) =>
              setData({
                ...data,
                stages: {
                  ...data.stages,
                  [activeStage]: { ...stage, d2: e.target.value },
                },
              })
            }
          />
        </CardContent>
      </Card>
    </div>
  );
}
