/** Mirrors fastapi `OBSERVER_LOGIN` — only this teacher login sees 研究分析. */
export const RESEARCH_OBSERVER_LOGIN = "allclass";

export function isResearchObserverLogin(login: string | null | undefined): boolean {
  return String(login ?? "").trim().toLowerCase() === RESEARCH_OBSERVER_LOGIN;
}
