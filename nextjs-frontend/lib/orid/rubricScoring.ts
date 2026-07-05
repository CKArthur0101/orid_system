/**
 * Client-side ORID + SEL rubric scoring helper.
 *
 * Mirrors the backend `orid_rubric_scoring.py` logic:
 *   ORID: O1 / R1 / I1 / D1 × 10 pts each = 40 pts max
 *   SEL:  SEL_EA / SEL_PT_R / SEL_VR / SEL_PT_I / SEL_RA × 10 pts each = 50 pts max
 *   Total max: 90
 *
 * Triangular cumulative scoring — reaching level n means levels 1..n are all achieved:
 *   1 →  1 pt   (= 1)
 *   2 →  3 pts  (= 1+2)
 *   3 →  6 pts  (= 1+2+3)
 *   4 → 10 pts  (= 1+2+3+4)
 *
 * Formula: triangularPoints(n) = n * (n + 1) / 2
 */

export const ORID_CRITERION_IDS = ["O1", "R1", "I1", "D1"] as const;
export const SEL_CRITERION_IDS = ["SEL_EA", "SEL_PT_R", "SEL_VR", "SEL_PT_I", "SEL_RA"] as const;

export const POINTS_PER_CRITERION = 10;
export const ORID_MAX = ORID_CRITERION_IDS.length * POINTS_PER_CRITERION; // 40
export const SEL_MAX = SEL_CRITERION_IDS.length * POINTS_PER_CRITERION;   // 50
export const TOTAL_MAX = 90;

type OridLevels = Partial<Record<(typeof ORID_CRITERION_IDS)[number], number | null>>;
type SelLevels = Partial<Record<(typeof SEL_CRITERION_IDS)[number], number | null>>;

export interface ScoreResult {
  oridSubtotal: number;
  selSubtotal: number;
  totalScore: number;        // clamped 0–90, integer
  maxTotal: 90;
  oridBreakdown: Record<string, number>;
  selBreakdown: Record<string, number>;
  missing: string[];
}

function triangularPoints(level: number): number {
  return (level * (level + 1)) / 2;
}

function scoreCriterion(level: number | null | undefined): number {
  if (level == null) return 0;
  if (level < 1 || level > 4) return 0;
  return triangularPoints(level);
}

function clamp(score: number): number {
  return Math.max(0, Math.min(TOTAL_MAX, Math.round(score)));
}

export function calculateOridSelScore(
  oridLevels: OridLevels,
  selLevels: SelLevels,
): ScoreResult {
  const oridBreakdown: Record<string, number> = {};
  const selBreakdown: Record<string, number> = {};
  const missing: string[] = [];

  for (const cid of ORID_CRITERION_IDS) {
    const lvl = oridLevels[cid];
    if (lvl == null) missing.push(cid);
    oridBreakdown[cid] = scoreCriterion(lvl);
  }
  for (const cid of SEL_CRITERION_IDS) {
    const lvl = selLevels[cid];
    if (lvl == null) missing.push(cid);
    selBreakdown[cid] = scoreCriterion(lvl);
  }

  const oridSubtotal = Object.values(oridBreakdown).reduce((a, b) => a + b, 0);
  const selSubtotal = Object.values(selBreakdown).reduce((a, b) => a + b, 0);
  const totalScore = clamp(oridSubtotal + selSubtotal);

  return {
    oridSubtotal: Math.round(oridSubtotal * 100) / 100,
    selSubtotal: Math.round(selSubtotal * 100) / 100,
    totalScore,
    maxTotal: 90,
    oridBreakdown,
    selBreakdown,
    missing,
  };
}

/** Format score for display: "50/90"; null/undefined shows as "0/90". */
export function formatScore(totalScore: number | null | undefined): string {
  const n = totalScore ?? 0;
  return `${n}/90`;
}
