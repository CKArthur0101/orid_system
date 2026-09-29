import {
  SYNTHESIS_BADGE_ORDER,
  calculateEarnedSynthesisBadges,
} from "@/lib/orid/badgeRules";

describe("even-week synthesis badges", () => {
  it("shows four independent badge slots", () => {
    expect(SYNTHESIS_BADGE_ORDER).toEqual([
      "badge_synthesis_content",
      "badge_synthesis_coherence",
      "badge_synthesis_reflection",
      "badge_synthesis_action",
    ]);
  });

  it("earns only criteria at level 3 or 4", () => {
    expect(
      calculateEarnedSynthesisBadges({
        content_integration: 3,
        coherence: 2,
        reflection_depth: 4,
        action_application: 1,
      }),
    ).toEqual(["badge_synthesis_content", "badge_synthesis_reflection"]);
  });

  it("does not award a badge from writing length or missing levels", () => {
    expect(calculateEarnedSynthesisBadges({})).toEqual([]);
  });
});
