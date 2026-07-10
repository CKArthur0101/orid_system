/**
 * Coach opening message for odd-week ORID writing sessions.
 *
 * Constructs a 4-element welcome:
 *   1. Mascot self-introduction
 *   2. Book title
 *   3. One-sentence story hook (from core_theme or key_events)
 *   4. An open-ended question to kick off the session
 */

type BookPackForOpening = {
  book_title?: string | null;
  core_theme?: string[] | null;
  key_events?: string[] | null;
};

/** Truncate a long string to roughly the first 35 characters at a natural break. */
function _shorten(text: string, max = 35): string {
  if (text.length <= max) return text;
  const cut = text.slice(0, max);
  const lastPunct = Math.max(cut.lastIndexOf("，"), cut.lastIndexOf("；"), cut.lastIndexOf("。"));
  return (lastPunct > 10 ? cut.slice(0, lastPunct) : cut) + "……";
}

/**
 * Build the full coach opening message.
 *
 * @param bookPack - Book metadata (may be null when the pack is loading).
 */
export function buildCoachOpeningMessage(bookPack: BookPackForOpening | null): string {
  const title = (bookPack?.book_title ?? "").trim();
  const book = title ? `《${title}》` : "這本書";

  // Story hook: prefer first key_event, fall back to first core_theme
  const events = bookPack?.key_events ?? [];
  const themes = bookPack?.core_theme ?? [];
  const rawHook = (events[0] || themes[0] || "").trim();
  const hook = rawHook ? _shorten(rawHook) : "";

  const lines: string[] = [
    `嗨！我是你的松果小夥伴 🌰`,
    `今天我們要聊 ${book}。`,
  ];

  if (hook) {
    lines.push(`故事裡${hook}`);
  }

  lines.push(
    `你讀完這本書之後，印象最深的是哪一幕呢？`,
  );

  return lines.join("\n");
}
