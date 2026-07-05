import { parseFeedbackNarration } from "@/lib/parse-feedback-narration";

describe("parseFeedbackNarration", () => {
  it("parses standard three-section narration", () => {
    const text = [
      "你已經做到：",
      "你有寫出主角做了什麼事。",
      "",
      "你可以再加強：",
      "再補一句當時發生在哪裡。",
      "",
      "試試看這樣寫：",
      "我看到＿＿＿在＿＿＿做了＿＿＿。",
    ].join("\n");

    expect(parseFeedbackNarration(text)).toEqual({
      praise: "你有寫出主角做了什麼事。",
      rethink: "再補一句當時發生在哪裡。",
      example: "我看到＿＿＿在＿＿＿做了＿＿＿。",
    });
  });

  it("parses 試著補一句 third heading", () => {
    const text = [
      "你已經做到：",
      "你有寫到「用柿子蒂打陀螺」。",
      "",
      "你可以再加強：",
      "再補上是誰帶著玩。",
      "",
      "試著補一句：",
      "在你寫的「一開始……」後面，加一句藏進倉庫。",
    ].join("\n");

    expect(parseFeedbackNarration(text)).toEqual({
      praise: "你有寫到「用柿子蒂打陀螺」。",
      rethink: "再補上是誰帶著玩。",
      example: "在你寫的「一開始……」後面，加一句藏進倉庫。",
    });
  });

  it("accepts shortened third heading", () => {
    const text = [
      "你已經做到：",
      "你有寫出感受。",
      "",
      "你可以再加強：",
      "可以再說明原因。",
      "",
      "試試看：",
      "我覺得＿＿＿，因為＿＿＿。",
    ].join("\n");

    const parsed = parseFeedbackNarration(text);
    expect(parsed?.praise).toBe("你有寫出感受。");
    expect(parsed?.rethink).toBe("可以再說明原因。");
    expect(parsed?.example).toBe("我覺得＿＿＿，因為＿＿＿。");
  });

  it("returns null when not feedback narration", () => {
    expect(parseFeedbackNarration("哈囉！我是你的寫作小幫手 🤖")).toBeNull();
  });

  it("does not treat inline 試試看這樣寫 as the third section heading", () => {
    const text = [
      "你已經做到：",
      "你有試著寫到「看到阿松爺爺吃地瓜」。",
      "",
      "你可以再加強：",
      "內容還有點短；也可以先看看下方「試試看這樣寫」的起頭，跟著接一句就好。",
      "",
      "試試看這樣寫：",
      "故事裡有柿子這一幕，你可以先問自己：誰做了什麼？",
    ].join("\n");

    const parsed = parseFeedbackNarration(text);
    expect(parsed?.rethink).toContain("內容還有點短");
    expect(parsed?.rethink).not.toMatch(/」的起頭$/);
    expect(parsed?.example).toContain("柿子");
  });
});
