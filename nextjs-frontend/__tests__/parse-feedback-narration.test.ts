/**
 * Tests for parseFeedbackNarration discriminated union.
 *
 * Covers:
 * - Complete card (本階段完成) parsed as kind="complete"
 * - Revision card (你可以再加強 / 再想一想) parsed as kind="revision"
 * - Legacy three-section messages still parse as kind="revision" (backward compat)
 * - Empty text returns null
 * - Missing headings return null
 * - Complete card has no rethink/example fields
 * - Control group messages (WritingPromptHelper format) do NOT parse as feedback cards
 */

import { parseFeedbackNarration, looksLikeFeedbackNarration } from "@/lib/parse-feedback-narration";

// ── Helper builders ──────────────────────────────────────────────────────────

function makeCompleteCard(stage: string, praise = "你已經把感受說清楚了。"): string {
  const completionMap: Record<string, string> = {
    O: "O 客觀事實階段完成！你已經把故事裡的人物和事件說清楚了。",
    R: "R 感受階段完成！你已經把自己的感受和原因說清楚了。",
    I: "I 意義階段完成！你已經寫出從故事裡學到了什麼。",
    D: "D 行動階段完成！你已經寫出之後想怎麼做了。",
  };
  const nextMap: Record<string, string> = {
    O: "接下來可以進入 R，試著寫寫看：這個故事哪一幕讓你印象最深？你有什麼感覺？",
    R: "接下來可以進入 I，試著想想：這個故事讓你明白了什麼道理？",
    I: "接下來可以進入 D，試著寫寫看：讀完之後，你在生活裡想怎麼做？",
    D: "四格都完成了！記得按「儲存我的寫作」把內容存起來。",
  };
  return [
    `你已經做到：\n${praise}`,
    `本階段完成：\n${completionMap[stage] ?? stage + " 階段完成！"}`,
    `下一步：\n${nextMap[stage] ?? "請繼續。"}`,
  ].join("\n\n");
}

function makeRevisionCard(rethink = "你可以再加強", example?: string): string {
  const parts = [
    "你已經做到：\n你有試著寫出感受。",
    `${rethink}：\n補上原因會更好。`,
    "試著補一句：\n我覺得＿＿＿，因為＿＿＿。",
  ];
  if (example) {
    parts[2] = `試著補一句：\n${example}`;
  }
  return parts.join("\n\n");
}

// ── Complete card tests ──────────────────────────────────────────────────────

describe("parseFeedbackNarration — complete card", () => {
  test.each(["O", "R", "I", "D"])("stage %s parses as kind=complete", (stage) => {
    const text = makeCompleteCard(stage);
    const parsed = parseFeedbackNarration(text);
    expect(parsed).not.toBeNull();
    expect(parsed!.kind).toBe("complete");
  });

  test("complete card has praise field", () => {
    const text = makeCompleteCard("R", "你已經把感受說清楚了。");
    const parsed = parseFeedbackNarration(text);
    expect(parsed!.kind).toBe("complete");
    if (parsed!.kind === "complete") {
      expect(parsed.praise).toBeTruthy();
      expect(parsed.completion).toBeTruthy();
      expect(parsed.nextStep).toBeTruthy();
    }
  });

  test("complete card has no rethink field", () => {
    const text = makeCompleteCard("R");
    const parsed = parseFeedbackNarration(text);
    expect(parsed!.kind).toBe("complete");
    expect((parsed as { rethink?: string }).rethink).toBeUndefined();
  });

  test("complete card has no example field", () => {
    const text = makeCompleteCard("I");
    const parsed = parseFeedbackNarration(text);
    expect(parsed!.kind).toBe("complete");
    expect((parsed as { example?: string }).example).toBeUndefined();
  });

  test("complete card without nextStep section still parses", () => {
    const text = "你已經做到：\n你有試著寫了。\n\n本階段完成：\nR 感受階段完成！";
    const parsed = parseFeedbackNarration(text);
    expect(parsed).not.toBeNull();
    expect(parsed!.kind).toBe("complete");
    if (parsed!.kind === "complete") {
      expect(parsed.nextStep).toBeUndefined();
    }
  });

  test("complete card does not contain modification language", () => {
    const text = makeCompleteCard("O");
    const FORBIDDEN = ["再補一句", "可以更具體", "再加入例子", "你可以再加強", "試著修改"];
    for (const phrase of FORBIDDEN) {
      expect(text).not.toContain(phrase);
    }
  });
});

// ── Revision card tests ──────────────────────────────────────────────────────

describe("parseFeedbackNarration — revision card", () => {
  test("你可以再加強 heading parses as revision", () => {
    const text = makeRevisionCard("你可以再加強");
    const parsed = parseFeedbackNarration(text);
    expect(parsed!.kind).toBe("revision");
  });

  test("再想一想 alternative heading parses as revision", () => {
    const text = makeRevisionCard("再想一想");
    const parsed = parseFeedbackNarration(text);
    expect(parsed!.kind).toBe("revision");
  });

  test("revision card has praise and rethink fields", () => {
    const text = makeRevisionCard();
    const parsed = parseFeedbackNarration(text);
    expect(parsed!.kind).toBe("revision");
    if (parsed!.kind === "revision") {
      expect(parsed.praise).toBeTruthy();
      expect(parsed.rethink).toBeTruthy();
    }
  });

  test("revision card with example has example field", () => {
    const text = makeRevisionCard("你可以再加強", "我覺得＿＿，因為＿＿。");
    const parsed = parseFeedbackNarration(text);
    expect(parsed!.kind).toBe("revision");
    if (parsed!.kind === "revision") {
      expect(parsed.example).toBeTruthy();
    }
  });
});

// ── Backward compatibility ───────────────────────────────────────────────────

describe("parseFeedbackNarration — backward compatibility", () => {
  test("old three-section 試試看 heading parses as revision", () => {
    const text =
      "你已經做到：\n你有把情節寫出來。\n\n再想一想：\n感受是什麼？\n\n試試看這樣寫：\n我覺得＿＿，因為＿＿。";
    const parsed = parseFeedbackNarration(text);
    expect(parsed).not.toBeNull();
    expect(parsed!.kind).toBe("revision");
  });

  test("可以這樣修改 heading parses as revision", () => {
    const text =
      "你已經做到：\n你有試著寫。\n\n你可以再加強：\n補原因。\n\n可以這樣修改：\n我覺得＿＿。";
    const parsed = parseFeedbackNarration(text);
    expect(parsed!.kind).toBe("revision");
  });
});

// ── Edge cases ───────────────────────────────────────────────────────────────

describe("parseFeedbackNarration — edge cases", () => {
  test("empty string returns null", () => {
    expect(parseFeedbackNarration("")).toBeNull();
  });

  test("plain text without headings returns null", () => {
    expect(parseFeedbackNarration("學生寫得很好！繼續加油。")).toBeNull();
  });

  test("text with only praise heading returns null (incomplete)", () => {
    expect(parseFeedbackNarration("你已經做到：\n你有試著寫。")).toBeNull();
  });

  test("control-group WritingPromptHelper text does NOT parse as feedback", () => {
    // Control group shows fixed prompt text, not structured feedback headings
    const promptText =
      "【O：客觀事實】\n故事裡發生了什麼事？誰做了什麼？先把最重要的事件寫出來。";
    expect(parseFeedbackNarration(promptText)).toBeNull();
  });

  test("looksLikeFeedbackNarration returns true for complete card", () => {
    expect(looksLikeFeedbackNarration(makeCompleteCard("R"))).toBe(true);
  });

  test("looksLikeFeedbackNarration returns true for revision card", () => {
    expect(looksLikeFeedbackNarration(makeRevisionCard())).toBe(true);
  });

  test("looksLikeFeedbackNarration returns false for plain text", () => {
    expect(looksLikeFeedbackNarration("學生寫得不錯。")).toBe(false);
  });
});

// ── Type narrowing verification ──────────────────────────────────────────────

describe("parseFeedbackNarration — TypeScript narrowing", () => {
  test("can narrow to complete and access completion field", () => {
    const parsed = parseFeedbackNarration(makeCompleteCard("D"));
    if (parsed && parsed.kind === "complete") {
      // TypeScript should allow this without type error
      const _comp: string = parsed.completion;
      expect(_comp).toBeTruthy();
    } else {
      throw new Error("Expected complete card");
    }
  });

  test("can narrow to revision and access rethink field", () => {
    const parsed = parseFeedbackNarration(makeRevisionCard());
    if (parsed && parsed.kind === "revision") {
      const _rethink: string = parsed.rethink;
      expect(_rethink).toBeTruthy();
    } else {
      throw new Error("Expected revision card");
    }
  });
});
