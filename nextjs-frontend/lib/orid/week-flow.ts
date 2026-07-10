/**
 * Week-parity helpers.
 *
 * Odd weeks (1, 3, 5, …) are ORID writing weeks.
 * Even weeks (2, 4, 6, …) are synthesis (integration) weeks that look back at
 * the preceding odd week.
 */

export const isOddWeek = (w: number): boolean => w % 2 === 1;
export const isEvenWeek = (w: number): boolean => w % 2 === 0;

/** The odd week directly before a given even week (e.g. 2 → 1, 4 → 3). */
export const priorOddWeek = (w: number): number => w - 1;

/**
 * 1-based book unit index derived from week number.
 * Weeks 1–2 → unit 1, weeks 3–4 → unit 2, etc.
 */
export const bookUnitFromWeek = (w: number): number => Math.ceil(w / 2);
