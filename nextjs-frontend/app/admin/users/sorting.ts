export type AdminUserForSort = {
  email: string;
  display_name: string | null;
  role: string;
  class_names: string[];
};

export type AdminUserSortField = "email" | "display_name" | "role" | "class";
export type AdminUserSortDirection = "asc" | "desc";

export type AdminUserSortConfig = {
  field: AdminUserSortField;
  direction: AdminUserSortDirection;
};

const roleRank: Record<string, number> = {
  student: 0,
  teacher: 1,
  admin: 2,
};

const collator = new Intl.Collator("en", {
  numeric: true,
  sensitivity: "base",
});

function compareNullableText(a: string | null | undefined, b: string | null | undefined) {
  const left = (a ?? "").trim();
  const right = (b ?? "").trim();
  if (!left && !right) return 0;
  if (!left) return 1;
  if (!right) return -1;
  return collator.compare(left, right);
}

function compareClassNames(a: AdminUserForSort, b: AdminUserForSort) {
  return compareNullableText(a.class_names[0], b.class_names[0]);
}

function hasClassName(user: AdminUserForSort) {
  return Boolean((user.class_names[0] ?? "").trim());
}

function compareUsers(a: AdminUserForSort, b: AdminUserForSort, field: AdminUserSortField) {
  if (field === "role") {
    return (roleRank[a.role] ?? 99) - (roleRank[b.role] ?? 99);
  }
  if (field === "display_name") {
    return compareNullableText(a.display_name, b.display_name);
  }
  if (field === "class") {
    return compareClassNames(a, b);
  }
  return collator.compare(a.email, b.email);
}

export function sortAdminUsers<T extends AdminUserForSort>(
  users: T[],
  sort: AdminUserSortConfig,
): T[] {
  const direction = sort.direction === "asc" ? 1 : -1;
  return [...users].sort((a, b) => {
    if (sort.field === "class" && hasClassName(a) !== hasClassName(b)) {
      return hasClassName(a) ? -1 : 1;
    }
    const primary = compareUsers(a, b, sort.field);
    if (primary !== 0) return primary * direction;
    return collator.compare(a.email, b.email);
  });
}
