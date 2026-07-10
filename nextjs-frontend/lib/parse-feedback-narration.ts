export type ParsedFeedbackNarration = {
  praise: string;
  rethink: string;
  example: string;
};

type HeadingMatch = {
  start: number;
  end: number;
};

function findHeading(text: string, pattern: RegExp): HeadingMatch | null {
  const anchored = new RegExp(`(?:^|\\n)${pattern.source}`, pattern.flags.includes("m") ? pattern.flags : `${pattern.flags}m`);
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
  const normalized = String(text ?? "").replace(/\r\n/g, "\n").trim();
  if (!normalized) return null;

  const praiseHeading = findHeading(normalized, /你已經做到[:：]?\s*/);
  const rethinkHeading =
    findHeading(normalized, /你可以再加強[:：]?\s*/) ??
    findHeading(normalized, /再想一想[:：]?\s*/);
  const exampleHeading =
    findHeading(normalized, /(?:試著補一句|試試看(?:這樣寫)?)[:：]?\s*/) ??
    findHeading(normalized, /可以這樣修改[:：]?\s*/);

  if (!praiseHeading || !rethinkHeading || !exampleHeading) return null;
  if (!(praiseHeading.start < rethinkHeading.start && rethinkHeading.start < exampleHeading.start)) return null;

  const praise = cleanSection(normalized.slice(praiseHeading.end, rethinkHeading.start));
  const rethink = cleanSection(normalized.slice(rethinkHeading.end, exampleHeading.start));
  const example = cleanSection(normalized.slice(exampleHeading.end));

  if (!praise || !rethink || !example) return null;
  return { praise, rethink, example };
}

export function looksLikeFeedbackNarration(text: string): boolean {
  return parseFeedbackNarration(text) !== null;
}
