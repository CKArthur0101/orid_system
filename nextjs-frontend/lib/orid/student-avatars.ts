export const STUDENT_AVATAR_EVENT = "orid:student-avatar";

const MAP_KEY = "orid-student-avatars";
const ACTIVE_KEY = "orid-student-avatar-active";

export type StudentAvatar = {
  id: string;
  group: "girl" | "boy";
  src: string;
  label: string;
};

export const STUDENT_AVATARS: StudentAvatar[] = [
  { id: "girl-1", group: "girl", src: "/images/orid/avatars/avatar-girl-1.png", label: "女生 1" },
  { id: "girl-2", group: "girl", src: "/images/orid/avatars/avatar-girl-2.png", label: "女生 2" },
  { id: "girl-3", group: "girl", src: "/images/orid/avatars/avatar-girl-3.png", label: "女生 3" },
  { id: "girl-4", group: "girl", src: "/images/orid/avatars/avatar-girl-4.png", label: "女生 4" },
  { id: "boy-1", group: "boy", src: "/images/orid/avatars/avatar-boy-1.png", label: "男生 1" },
  { id: "boy-2", group: "boy", src: "/images/orid/avatars/avatar-boy-2.png", label: "男生 2" },
  { id: "boy-3", group: "boy", src: "/images/orid/avatars/avatar-boy-3.png", label: "男生 3" },
  { id: "boy-4", group: "boy", src: "/images/orid/avatars/avatar-boy-4.png", label: "男生 4" },
];

export function studentAvatarKey(user: { id?: string | null; email?: string | null }) {
  return String(user.id || user.email || "student").trim().toLowerCase();
}

export function avatarSrcForId(id: string | null | undefined) {
  return STUDENT_AVATARS.find((avatar) => avatar.id === id)?.src ?? null;
}

function readMap(): Record<string, string> {
  if (typeof window === "undefined") return {};
  try {
    const raw = window.localStorage.getItem(MAP_KEY);
    const parsed = raw ? JSON.parse(raw) : {};
    return parsed && typeof parsed === "object" ? (parsed as Record<string, string>) : {};
  } catch {
    return {};
  }
}

export function readActiveAvatarId() {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem(ACTIVE_KEY);
}

export function activateStoredAvatar(userKey: string) {
  const id = readMap()[userKey] ?? null;
  if (typeof window === "undefined") return id;
  if (id) window.localStorage.setItem(ACTIVE_KEY, id);
  else window.localStorage.removeItem(ACTIVE_KEY);
  window.dispatchEvent(new CustomEvent(STUDENT_AVATAR_EVENT, { detail: id }));
  return id;
}

export function saveStudentAvatar(userKey: string, id: string) {
  const map = readMap();
  map[userKey] = id;
  window.localStorage.setItem(MAP_KEY, JSON.stringify(map));
  window.localStorage.setItem(ACTIVE_KEY, id);
  window.dispatchEvent(new CustomEvent(STUDENT_AVATAR_EVENT, { detail: id }));
}
