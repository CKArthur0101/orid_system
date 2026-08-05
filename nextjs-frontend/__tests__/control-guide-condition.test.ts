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

  test("book2/book3 fall back to generic (no Book-1 names)", () => {
    for (const bookId of ["book2", "book3", "generic"] as const) {
      const texts = getControlGuidePages("I", bookId)
        .map((p) => p.text)
        .join("\n");
      expect(texts).not.toContain("阿松爺爺");
      expect(texts).not.toContain("哎唷奶奶");
    }
  });

  test("synthesis pages remain available", () => {
    expect(getSynthesisGuidePages("book1").length).toBeGreaterThan(0);
    expect(getSynthesisGuidePages("book2").length).toBeGreaterThan(0);
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
