"use client";

import { useMemo } from "react";
import { Card, CardContent } from "@/components/ui/card";

export type StageKey = "O" | "R" | "I" | "D";
export type ConditionKey = "genai" | "template";

export type StageDraft = {
  d1: string;
  d2: string;
  done?: boolean; // 可選：標記本段完成
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
  currentStageFromChat: string; // 來自聊天 currentStage
  condition: ConditionKey;
}) {
  const { data, setData, activeStage, setActiveStage, currentStageFromChat, condition } = props;

  // 解鎖規則（先做簡單版）：允許「目前聊天階段」與「之前階段」可寫
  const unlockedIndex = useMemo(() => {
    const i = idxOfStage(currentStageFromChat || "O");
    return i < 0 ? 0 : i;
  }, [currentStageFromChat]);

  const activeIndex = idxOfStage(activeStage);

  const locked = activeIndex > unlockedIndex;

  const feedbackText = useMemo(() => {
    // 前端先做「展示用」：實驗組顯示個人化提示的“型態”，對照組顯示固定檢核規則
    if (condition === "genai") {
      return [
        "• 根據你這段的內容，系統會指出缺漏（情緒/原因/換位/行動可檢核）",
        "• 並提供下一句可以怎麼補的具體方向（不直接幫你代寫）",
      ].join("\n");
    }
    return [
      "• 固定模板檢核（不個人化、不生成改寫）",
      "• 例：至少兩句、需包含「因為」、需連回故事線索、D 段需具體做法",
    ].join("\n");
  }, [condition]);

  const stage = data.stages[activeStage];

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
                "rounded-full border px-3 py-1 text-xs",
                isActive ? "bg-primary text-primary-foreground border-primary" : "bg-muted/30",
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
        <div className="text-xs text-muted-foreground">
          目前聊天尚未到這一段，請先完成前面對話再寫。
        </div>
      )}

      {/* Draft 1 */}
      <Card>
        <CardContent className="p-4 space-y-2">
          <div className="text-sm font-medium">Draft 1（第一稿）</div>
          <textarea
            disabled={locked}
            className="min-h-[170px] w-full rounded-md border bg-background p-3 text-sm outline-none"
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

      {/* Feedback (展示區) */}
      <Card>
        <CardContent className="p-4 space-y-2">
          <div className="text-sm font-medium">回饋提示（兩組差異在這裡）</div>
          <pre className="whitespace-pre-wrap text-xs text-muted-foreground">{feedbackText}</pre>
        </CardContent>
      </Card>

      {/* Draft 2 */}
      <Card>
        <CardContent className="p-4 space-y-2">
          <div className="text-sm font-medium">Draft 2（修訂稿）</div>
          <textarea
            disabled={locked}
            className="min-h-[170px] w-full rounded-md border bg-background p-3 text-sm outline-none"
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
