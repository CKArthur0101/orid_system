import {
  controlGuideBookIdFromWeek,
  getControlGuidePages,
  getSynthesisGuidePages,
} from "@/lib/orid/control-guide-pages";
import { buildSynthesisOpeningMessage } from "@/lib/orid/synthesis-opening";

describe("control-guide-pages parameterization", () => {
  test("week maps to book ids", () => {
    expect(controlGuideBookIdFromWeek(1)).toBe("book1");
    expect(controlGuideBookIdFromWeek(2)).toBe("book1");
    expect(controlGuideBookIdFromWeek(3)).toBe("book2");
    expect(controlGuideBookIdFromWeek(5)).toBe("book3");
  });

  test("book1 keeps character-grounded SEL prompts", () => {
    const pages = getControlGuidePages("R", "book1");
    const texts = pages.map((p) => p.text).join("\n");
    expect(texts).toContain("阿松爺爺");
  });

  test("book2 has character-grounded prompts (朱家人物), not book1 names", () => {
    const texts = getControlGuidePages("O", "book2").map((p) => p.text).join("\n");
    expect(texts).toContain("朱太太");
    expect(texts).not.toContain("阿松爺爺");
    expect(texts).not.toContain("哎唷奶奶");
  });

  test("book3 has character-grounded prompts (獅子), not book1 or book2 names", () => {
    const allStages: Array<"O" | "R" | "I" | "D"> = ["O", "R", "I", "D"];
    for (const stage of allStages) {
      const texts = getControlGuidePages(stage, "book3").map((p) => p.text).join("\n");
      expect(texts).toContain("獅子");
      expect(texts).not.toContain("阿松爺爺");
      expect(texts).not.toContain("哎唷奶奶");
      expect(texts).not.toContain("朱太太");
      expect(texts).not.toContain("朱先生");
      // 確認無 SEL 術語、rubric、分數等字樣出現在控制組提示卡
      expect(texts).not.toContain("SEL");
      expect(texts).not.toContain("rubric");
      expect(texts).not.toContain("分數");
    }
  });

  test("generic still works as fallback (no specific book character names)", () => {
    const texts = getControlGuidePages("I", "generic")
      .map((p) => p.text)
      .join("\n");
    expect(texts).not.toContain("阿松爺爺");
    expect(texts).not.toContain("哎唷奶奶");
    expect(texts).not.toContain("朱太太");
    expect(texts).not.toContain("獅子");
  });

  test("synthesis pages remain available", () => {
    expect(getSynthesisGuidePages("book1").length).toBeGreaterThan(0);
    expect(getSynthesisGuidePages("book2").length).toBeGreaterThan(0);
  });

  test("each topic has one main item and two fixed supporting items", () => {
    const oddWeekPages = getControlGuidePages("O", "book1");
    const synthesisPages = getSynthesisGuidePages("book1");

    for (const pages of [oddWeekPages, synthesisPages]) {
      const prompts = pages.filter((page) => page.track === "sel");
      const sentenceFrames = pages.filter((page) => page.track === "orid");

      expect(prompts).toHaveLength(4);
      expect(sentenceFrames).toHaveLength(4);
      expect(prompts.every((page) => page.supportingTexts?.length === 2)).toBe(true);
      expect(sentenceFrames.every((page) => page.supportingTexts?.length === 2)).toBe(true);
    }
  });
});

describe("buildSynthesisOpeningMessage condition wording", () => {
  test("experimental mentions 取得整合回饋", () => {
    const text = buildSynthesisOpeningMessage(null, "測試書", 2);
    expect(text).toContain("取得整合回饋");
  });

  test("control points to fixed prompts instead", () => {
    const text = buildSynthesisOpeningMessage(null, "測試書", 2, { isControl: true });
    expect(text).not.toContain("取得整合回饋");
    expect(text).toContain("整合寫作提示");
  });
});
