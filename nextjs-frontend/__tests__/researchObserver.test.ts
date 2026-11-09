import { isResearchObserverLogin, RESEARCH_OBSERVER_LOGIN } from "@/lib/orid/research-observer";

describe("isResearchObserverLogin", () => {
  it("only matches the allclass observer login", () => {
    expect(RESEARCH_OBSERVER_LOGIN).toBe("allclass");
    expect(isResearchObserverLogin("allclass")).toBe(true);
    expect(isResearchObserverLogin("AllClass")).toBe(true);
    expect(isResearchObserverLogin("501teacher")).toBe(false);
    expect(isResearchObserverLogin("")).toBe(false);
    expect(isResearchObserverLogin(null)).toBe(false);
  });
});
