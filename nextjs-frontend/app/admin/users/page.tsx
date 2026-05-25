"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { ArrowDown, ArrowUp, ArrowUpDown, Pencil, Plus, Trash2 } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  sortAdminUsers,
  type AdminUserSortConfig,
  type AdminUserSortDirection,
  type AdminUserSortField,
} from "./sorting";

type AdminClass = {
  id: string;
  name: string;
  year: number;
  external_code: string | null;
  student_count: number;
  teacher_count: number;
};

type AdminUser = {
  id: string;
  email: string;
  display_name: string | null;
  role: string;
  is_active: boolean;
  class_names: string[];
  class_ids: string[];
};

type UserForm = {
  email: string;
  display_name: string;
  password: string;
  role: "student" | "teacher";
  class_ids: string[];
  is_active: boolean;
};

const emptyForm = (): UserForm => ({
  email: "",
  display_name: "",
  password: "",
  role: "student",
  class_ids: [],
  is_active: true,
});

const ROLE_LABEL: Record<string, string> = {
  student: "學生",
  teacher: "教師",
  admin: "管理員",
};

function nextSortDirection(
  field: AdminUserSortField,
  sort: AdminUserSortConfig,
): AdminUserSortDirection {
  if (sort.field !== field) return "asc";
  return sort.direction === "asc" ? "desc" : "asc";
}

function SortableTableHead({
  field,
  label,
  sort,
  onSort,
}: {
  field: AdminUserSortField;
  label: string;
  sort: AdminUserSortConfig;
  onSort: (field: AdminUserSortField) => void;
}) {
  const isActive = sort.field === field;
  const Icon = isActive ? (sort.direction === "asc" ? ArrowUp : ArrowDown) : ArrowUpDown;
  const nextDirection = nextSortDirection(field, sort);

  return (
    <TableHead aria-sort={isActive ? (sort.direction === "asc" ? "ascending" : "descending") : "none"}>
      <button
        type="button"
        onClick={() => onSort(field)}
        className="inline-flex items-center gap-1 rounded px-1 py-0.5 text-left font-medium text-slate-600 transition hover:bg-slate-100 hover:text-slate-900"
        title={`依${label}${nextDirection === "asc" ? "升冪" : "降冪"}排序`}
      >
        {label}
        <Icon className={isActive ? "h-3.5 w-3.5 text-blue-600" : "h-3.5 w-3.5 text-slate-400"} />
      </button>
    </TableHead>
  );
}

export default function AdminUsersPage() {
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [classes, setClasses] = useState<AdminClass[]>([]);
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [modalOpen, setModalOpen] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [form, setForm] = useState<UserForm>(emptyForm());
  const [saving, setSaving] = useState(false);
  const [passwordOnce, setPasswordOnce] = useState<string | null>(null);
  const [sort, setSort] = useState<AdminUserSortConfig>({ field: "email", direction: "asc" });

  const sortedUsers = useMemo(() => sortAdminUsers(users, sort), [users, sort]);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const qs = search.trim() ? `?q=${encodeURIComponent(search.trim())}&page_size=200` : "?page_size=200";
      const [uRes, cRes] = await Promise.all([
        fetch(`/api/admin/users${qs}`, { cache: "no-store" }),
        fetch("/api/admin/classes", { cache: "no-store" }),
      ]);
      if (!uRes.ok) throw new Error(await uRes.text());
      if (!cRes.ok) throw new Error(await cRes.text());
      const uData = await uRes.json();
      setUsers(uData.items ?? []);
      setClasses(await cRes.json());
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "載入失敗");
    } finally {
      setLoading(false);
    }
  }, [search]);

  useEffect(() => {
    void load();
  }, [load]);

  function openCreate() {
    setEditingId(null);
    setForm(emptyForm());
    setPasswordOnce(null);
    setModalOpen(true);
  }

  function openEdit(u: AdminUser) {
    if (u.role === "admin") {
      setError("管理員帳號請用種子腳本維護，無法在此編輯。");
      return;
    }
    setEditingId(u.id);
    setForm({
      email: u.email,
      display_name: u.display_name ?? "",
      password: "",
      role: u.role === "teacher" ? "teacher" : "student",
      class_ids: [...u.class_ids],
      is_active: u.is_active,
    });
    setPasswordOnce(null);
    setModalOpen(true);
  }

  function toggleClass(classId: string) {
    setForm((prev) => {
      const has = prev.class_ids.includes(classId);
      return {
        ...prev,
        class_ids: has ? prev.class_ids.filter((id) => id !== classId) : [...prev.class_ids, classId],
      };
    });
  }

  function handleSort(field: AdminUserSortField) {
    setSort((prev) => {
      if (prev.field !== field) {
        return { field, direction: "asc" };
      }
      return { field, direction: prev.direction === "asc" ? "desc" : "asc" };
    });
  }

  async function handleSave(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    setError(null);
    try {
      if (editingId) {
        const body: Record<string, unknown> = {
          email: form.email.trim(),
          display_name: form.display_name.trim() || null,
          role: form.role,
          is_active: form.is_active,
          class_ids: form.class_ids,
        };
        if (form.password.trim()) body.new_password = form.password.trim();
        const r = await fetch(`/api/admin/users/${editingId}`, {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
        });
        const text = await r.text();
        if (!r.ok) throw new Error(text);
        const data = JSON.parse(text);
        if (data.password_once) setPasswordOnce(data.password_once);
        else {
          setModalOpen(false);
        }
      } else {
        if (!form.password.trim()) {
          setError("請設定密碼");
          setSaving(false);
          return;
        }
        const r = await fetch("/api/admin/users", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            email: form.email.trim(),
            display_name: form.display_name.trim() || null,
            password: form.password.trim(),
            role: form.role,
            class_ids: form.class_ids,
          }),
        });
        const text = await r.text();
        if (!r.ok) throw new Error(text);
        const data = JSON.parse(text);
        setPasswordOnce(data.password_once ?? form.password.trim());
      }
      await load();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "儲存失敗");
    } finally {
      setSaving(false);
    }
  }

  async function handleDelete(u: AdminUser) {
    if (u.role === "admin") {
      setError("無法刪除管理員帳號");
      return;
    }
    if (!confirm(`確定刪除 ${u.email}？此操作無法復原。`)) return;
    const r = await fetch(`/api/admin/users/${u.id}`, { method: "DELETE" });
    if (!r.ok && r.status !== 204) {
      setError(await r.text());
      return;
    }
    await load();
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-800">使用者管理</h1>
          <p className="text-sm text-slate-500">建立帳號、設定角色與班級、重設密碼</p>
        </div>
        <Button onClick={openCreate} className="gap-1">
          <Plus className="h-4 w-4" />
          新增使用者
        </Button>
      </div>

      <Card>
        <CardHeader className="pb-3">
          <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
            <CardTitle className="text-base">使用者列表</CardTitle>
            <Input
              placeholder="搜尋帳號或顯示名稱…"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="max-w-xs"
            />
            <Button variant="outline" size="sm" onClick={() => void load()}>
              重新整理
            </Button>
          </div>
        </CardHeader>
        <CardContent>
          {error && !modalOpen && (
            <p className="mb-3 text-sm text-red-600 whitespace-pre-wrap">{error}</p>
          )}
          {loading ? (
            <p className="text-sm text-slate-500">載入中…</p>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <SortableTableHead field="email" label="登入帳號" sort={sort} onSort={handleSort} />
                  <SortableTableHead field="display_name" label="顯示名稱" sort={sort} onSort={handleSort} />
                  <SortableTableHead field="role" label="角色" sort={sort} onSort={handleSort} />
                  <SortableTableHead field="class" label="班級" sort={sort} onSort={handleSort} />
                  <TableHead>密碼</TableHead>
                  <TableHead>狀態</TableHead>
                  <TableHead className="text-right">操作</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {sortedUsers.map((u) => (
                  <TableRow key={u.id}>
                    <TableCell className="font-medium">{u.email}</TableCell>
                    <TableCell>{u.display_name || "—"}</TableCell>
                    <TableCell>{ROLE_LABEL[u.role] ?? u.role}</TableCell>
                    <TableCell>
                      <div className="flex flex-wrap gap-1">
                        {u.class_names.length
                          ? u.class_names.map((n) => (
                              <Badge key={n} variant="secondary">
                                {n}
                              </Badge>
                            ))
                          : "—"}
                      </div>
                    </TableCell>
                    <TableCell className="text-slate-400">***</TableCell>
                    <TableCell>{u.is_active ? "啟用" : "停用"}</TableCell>
                    <TableCell className="text-right">
                      {u.role !== "admin" && (
                        <div className="flex justify-end gap-1">
                          <Button variant="ghost" size="sm" onClick={() => openEdit(u)}>
                            <Pencil className="h-4 w-4" />
                          </Button>
                          <Button variant="ghost" size="sm" onClick={() => void handleDelete(u)}>
                            <Trash2 className="h-4 w-4 text-red-500" />
                          </Button>
                        </div>
                      )}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      {modalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
          <div className="max-h-[90vh] w-full max-w-lg overflow-y-auto rounded-xl bg-white p-6 shadow-xl">
            <h2 className="text-lg font-bold">{editingId ? "編輯使用者" : "新增使用者"}</h2>
            {passwordOnce ? (
              <div className="mt-4 space-y-3">
                <p className="text-sm text-slate-600">請複製以下密碼（只顯示這一次）：</p>
                <div className="rounded-lg border bg-slate-50 p-3 font-mono text-sm">{passwordOnce}</div>
                <div className="flex gap-2">
                  <Button
                    type="button"
                    onClick={() => {
                      void navigator.clipboard.writeText(passwordOnce);
                    }}
                  >
                    複製密碼
                  </Button>
                  <Button
                    type="button"
                    variant="outline"
                    onClick={() => {
                      setPasswordOnce(null);
                      setModalOpen(false);
                    }}
                  >
                    關閉
                  </Button>
                </div>
              </div>
            ) : (
              <form onSubmit={(e) => void handleSave(e)} className="mt-4 space-y-4">
                {error && <p className="text-sm text-red-600 whitespace-pre-wrap">{error}</p>}
                <div className="space-y-2">
                  <Label htmlFor="email">登入帳號</Label>
                  <Input
                    id="email"
                    value={form.email}
                    onChange={(e) => setForm({ ...form, email: e.target.value })}
                    required
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="display_name">顯示名稱</Label>
                  <Input
                    id="display_name"
                    value={form.display_name}
                    onChange={(e) => setForm({ ...form, display_name: e.target.value })}
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="password">{editingId ? "新密碼（留空則不變）" : "密碼"}</Label>
                  <Input
                    id="password"
                    type="text"
                    autoComplete="new-password"
                    value={form.password}
                    onChange={(e) => setForm({ ...form, password: e.target.value })}
                    required={!editingId}
                    placeholder="至少 6 字，含英文與數字"
                  />
                </div>
                <div className="space-y-2">
                  <Label>角色</Label>
                  <Select
                    value={form.role}
                    onValueChange={(v) => setForm({ ...form, role: v as "student" | "teacher" })}
                  >
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="student">學生</SelectItem>
                      <SelectItem value="teacher">教師</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <div className="space-y-2">
                  <Label>班級（可複選）</Label>
                  <div className="max-h-40 space-y-2 overflow-y-auto rounded-md border p-3">
                    {classes.length === 0 && (
                      <p className="text-sm text-slate-500">尚無班級，請先到「班級」頁建立。</p>
                    )}
                    {classes.map((c) => (
                      <label key={c.id} className="flex cursor-pointer items-center gap-2 text-sm">
                        <input
                          type="checkbox"
                          checked={form.class_ids.includes(c.id)}
                          onChange={() => toggleClass(c.id)}
                        />
                        {c.name}
                      </label>
                    ))}
                  </div>
                </div>
                {editingId && (
                  <label className="flex items-center gap-2 text-sm">
                    <input
                      type="checkbox"
                      checked={form.is_active}
                      onChange={(e) => setForm({ ...form, is_active: e.target.checked })}
                    />
                    帳號啟用
                  </label>
                )}
                <div className="flex justify-end gap-2 pt-2">
                  <Button type="button" variant="outline" onClick={() => setModalOpen(false)}>
                    取消
                  </Button>
                  <Button type="submit" disabled={saving}>
                    {saving ? "儲存中…" : "儲存"}
                  </Button>
                </div>
              </form>
            )}
          </div>
        </div>
      )}
    </div>
  );
}