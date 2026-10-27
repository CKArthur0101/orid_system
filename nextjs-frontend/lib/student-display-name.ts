type NamedAccount = {
  display_name?: string | null;
  email?: string | null;
};

const DEMO_SUFFIX = "老師體驗";

function rawName(user: NamedAccount): string {
  return String(user.display_name ?? "").trim() || String(user.email ?? "").trim();
}

export function studentHeaderName(user: NamedAccount): string {
  const display = String(user.display_name ?? "").trim();
  if (display.endsWith(DEMO_SUFFIX)) {
    return `${display.slice(0, -DEMO_SUFFIX.length)} 老師`;
  }
  const name = rawName(user);
  return name ? `${name} 同學` : "";
}

export function studentHelloLine(user: NamedAccount): string {
  const display = String(user.display_name ?? "").trim();
  if (display.endsWith(DEMO_SUFFIX)) {
    return `哈囉，${display.slice(0, -DEMO_SUFFIX.length)} 老師！`;
  }
  const name = rawName(user);
  return name ? `哈囉，${name}同學！` : "哈囉！";
}
