import { sortAdminUsers, type AdminUserSortConfig } from "@/app/admin/users/sorting";

const users = [
  {
    id: "1",
    email: "teacher02",
    display_name: "王老師",
    role: "teacher",
    is_active: true,
    class_names: ["DILAB"],
    class_ids: ["c1"],
  },
  {
    id: "2",
    email: "student01",
    display_name: "陳學生",
    role: "student",
    is_active: true,
    class_names: ["朝陽國小"],
    class_ids: ["c2"],
  },
  {
    id: "3",
    email: "orid_admin",
    display_name: "ORID 管理員",
    role: "admin",
    is_active: true,
    class_names: [],
    class_ids: [],
  },
  {
    id: "4",
    email: "student02",
    display_name: null,
    role: "student",
    is_active: false,
    class_names: [],
    class_ids: [],
  },
];

function emailsFor(sort: AdminUserSortConfig) {
  return sortAdminUsers(users, sort).map((user) => user.email);
}

describe("sortAdminUsers", () => {
  it("sorts by login account in ascending and descending order", () => {
    expect(emailsFor({ field: "email", direction: "asc" })).toEqual([
      "orid_admin",
      "student01",
      "student02",
      "teacher02",
    ]);

    expect(emailsFor({ field: "email", direction: "desc" })).toEqual([
      "teacher02",
      "student02",
      "student01",
      "orid_admin",
    ]);
  });

  it("sorts roles with students first, then teachers, then admins", () => {
    expect(emailsFor({ field: "role", direction: "asc" })).toEqual([
      "student01",
      "student02",
      "teacher02",
      "orid_admin",
    ]);
  });

  it("sorts by first class name and keeps users without classes last", () => {
    expect(emailsFor({ field: "class", direction: "asc" })).toEqual([
      "teacher02",
      "student01",
      "orid_admin",
      "student02",
    ]);

    expect(emailsFor({ field: "class", direction: "desc" })).toEqual([
      "student01",
      "teacher02",
      "orid_admin",
      "student02",
    ]);
  });
});
