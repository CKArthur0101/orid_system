/**
 * Parses a structured AI feedback reply into a typed discriminated union.
 *
 * Revision card  (fb_ok=false, narration LLM output):
 *   你已經做到：  …
 *   你可以再加強：  …   (or 再想一想：)
 *   試著補一句：  …    (or 試試看…, 可以這樣修改：)
 *
 * Complete card  (fb_ok=true, deterministic formatter output):
 *   你已經做到：  …
 *   本階段完成：  …
 *   下一步：      …
 *
 * Legacy three-section messages from before this change are still parsed as
 * "revision" cards so chat history continues to display correctly.
 */

export type ParsedFeedbackNarration =
  | {
      kind: "revision";
      praise: string;
      rethink: string;
      example?: string;
    }
  | {
      kind: "complete";
      praise: string;
      completion: string;
      nextStep?: string;
    };

type HeadingMatch = {
  start: number;
  end: number;
};

function findHeading(text: string, pattern: RegExp): HeadingMatch | null {
  const anchored = new RegExp(
    `(?:^|\\n)${pattern.source}`,
    pattern.flags.includes("m") ? pattern.flags : `${pattern.flags}m`,
  );
  const match = anchored.exec(text);
  if (!match || match.index < 0) return null;
  const full = match[0];
  const labelEnd = match.index + full.length;
  return { start: match.index, end: labelEnd };
}

function cleanSection(raw: string): string {
  return raw.replace(/^\s+/, "").replace(/\s+$/, "");
}

export function parseFeedbackNarration(text: string): ParsedFeedbackNarration | null {
  const normalized = String(text ?? "")
    .replace(/\r\n/g, "\n")
    .trim();
  if (!normalized) return null;

  const praiseHeading = findHeading(normalized, /你已經做到[:：]?\s*/);
  if (!praiseHeading) return null;

  // ── Try complete card first ──────────────────────────────────────────────
  const completionHeading = findHeading(normalized, /本階段完成[:：]?\s*/);
  if (completionHeading && completionHeading.start > praiseHeading.start) {
    const nextStepHeading = findHeading(normalized, /下一步[:：]?\s*/);
    const praiseText = cleanSection(
      normalized.slice(
        praiseHeading.end,
        completionHeading.start,
      ),
    );
    const completionText = cleanSection(
      normalized.slice(
        completionHeading.end,
        nextStepHeading ? nextStepHeading.start : normalized.length,
      ),
    );
    const nextStepText = nextStepHeading
      ? cleanSection(normalized.slice(nextStepHeading.end))
      : undefined;

    if (praiseText && completionText) {
      return {
        kind: "complete",
        praise: praiseText,
        completion: completionText,
        ...(nextStepText ? { nextStep: nextStepText } : {}),
      };
    }
  }

  // ── Try revision card ────────────────────────────────────────────────────
  const rethinkHeading =
    findHeading(normalized, /你可以再加強[:：]?\s*/) ??
    findHeading(normalized, /再想一想[:：]?\s*/);
  const exampleHeading =
    findHeading(normalized, /(?:試著補一句|試試看(?:這樣寫)?)[:：]?\s*/) ??
    findHeading(normalized, /可以這樣修改[:：]?\s*/);

  if (!rethinkHeading || !exampleHeading) return null;
  if (
    !(
      praiseHeading.start < rethinkHeading.start &&
      rethinkHeading.start < exampleHeading.start
    )
  )
    return null;

  const praise = cleanSection(
    normalized.slice(praiseHeading.end, rethinkHeading.start),
  );
  const rethink = cleanSection(
    normalized.slice(rethinkHeading.end, exampleHeading.start),
  );
  const example = cleanSection(normalized.slice(exampleHeading.end));

  if (!praise || !rethink) return null;
  return {
    kind: "revision",
    praise,
    rethink,
    ...(example ? { example } : {}),
  };
}

export function looksLikeFeedbackNarration(text: string): boolean {
  return parseFeedbackNarration(text) !== null;
}
