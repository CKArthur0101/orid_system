"use client";

import { useCallback, useEffect, useState } from "react";
import { Plus, Trash2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";

type AdminClass = {
  id: string;
  name: string;
  year: number;
  external_code: string | null;
  study_condition?: string | null;
  archived_at?: string | null;
  student_count: number;
  teacher_count: number;
};

type DryRun = {
  students_to_create: number;
  teachers_to_create: number;
  skipped_507: number;
  skipped_existing: number;
  conflicts?: number;
  errors?: number;
  conflict_logins?: string[];
  error_reasons?: string[];
  error_logins?: string[];
  classes?: { code: string; study_condition: string; students: number }[];
  ok?: boolean;
};

export default function AdminClassesPage() {
  const [classes, setClasses] = useState<AdminClass[]>([]);
  const [includeArchived, setIncludeArchived] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [name, setName] = useState("");
  const [externalCode, setExternalCode] = useState("");
  const [saving, setSaving] = useState(false);
  const [rosterFile, setRosterFile] = useState<File | null>(null);
  const [dryRun, setDryRun] = useState<DryRun | null>(null);
  const [createdLogins, setCreatedLogins] = useState<string[]>([]);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const qs = includeArchived ? "?include_archived=1" : "";
      const r = await fetch(`/api/admin/classes${qs}`, { cache: "no-store" });
      if (!r.ok) throw new Error(await r.text());
      setClasses(await r.json());
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "載入失敗");
    } finally {
      setLoading(false);
    }
  }, [includeArchived]);

  useEffect(() => {
    void load();
  }, [load]);

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    if (!name.trim()) return;
    setSaving(true);
    setError(null);
    try {
      const r = await fetch("/api/admin/classes", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name: name.trim(),
          year: new Date().getFullYear(),
          external_code: externalCode.trim() || null,
        }),
      });
      if (!r.ok) throw new Error(await r.text());
      setName("");
      setExternalCode("");
      await load();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "建立失敗");
    } finally {
      setSaving(false);
    }
  }

  async function handleDelete(cls: AdminClass) {
    if (!confirm(`確定刪除班級「${cls.name}」？`)) return;
    const r = await fetch(`/api/admin/classes/${cls.id}`, { method: "DELETE" });
    if (!r.ok && r.status !== 204) {
      setError(await r.text());
      return;
    }
    await load();
  }

  async function handleArchive(cls: AdminClass) {
    const r = await fetch(`/api/admin/classes/${cls.id}/archive`, { method: "POST" });
    if (!r.ok) {
      setError(await r.text());
      return;
    }
    await load();
  }

  async function handleArchiveLegacy() {
    const r = await fetch("/api/admin/experiment/archive-legacy", { method: "POST" });
    if (!r.ok) {
      setError(await r.text());
      return;
    }
    await load();
  }

  async function postRoster(path: string) {
    if (!rosterFile) return null;
    const body = new FormData();
    body.append("file", rosterFile);
    const r = await fetch(path, { method: "POST", body });
    const text = await r.text();
    if (!r.ok) throw new Error(text);
    return JSON.parse(text) as DryRun & { created_logins?: string[] };
  }

  async function handleDryRun() {
    setError(null);
    setCreatedLogins([]);
    try {
      const data = await postRoster("/api/admin/experiment/dry-run");
      if (!data) return;
      setDryRun(data);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "乾跑失敗");
    }
  }

  async function handleImport() {
    if (!dryRun?.ok) return;
    if (!confirm("確認後會一次建立班級、學生與導師。任一衝突會整批中止。")) return;
    setError(null);
    try {
      const data = await postRoster("/api/admin/experiment/import");
      if (!data) return;
      setDryRun(data);
      setCreatedLogins(data.created_logins ?? []);
      await load();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "匯入失敗");
    }
  }

  function printSlips() {
    const lines = createdLogins.map((login) => `${login}　密碼：${login}`).join("\n");
    const popup = window.open("", "_blank", "noopener,noreferrer");
    if (!popup) return;
    popup.document.write(`<pre>${lines}</pre>`);
    popup.document.close();
    popup.print();
  }

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-2xl font-bold text-slate-800">班級管理</h1>
        <p className="text-sm text-slate-500">建立班級後，可在使用者頁指定學生／教師所屬班級</p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">新增班級</CardTitle>
        </CardHeader>
        <CardContent>
          <form onSubmit={(e) => void handleCreate(e)} className="flex flex-col gap-3 sm:flex-row sm:items-end">
            <div className="space-y-1 flex-1">
              <Label htmlFor="class-name">班級名稱</Label>
              <Input
                id="class-name"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="例如：501"
                required
              />
            </div>
            <div className="space-y-1 flex-1">
              <Label htmlFor="class-code">外部代碼（選填）</Label>
              <Input
                id="class-code"
                value={externalCode}
                onChange={(e) => setExternalCode(e.target.value)}
                placeholder="例如：501"
              />
            </div>
            <Button type="submit" disabled={saving} className="gap-1">
              <Plus className="h-4 w-4" />
              建立
            </Button>
          </form>
          {error && <p className="mt-2 text-sm text-red-600 whitespace-pre-wrap">{error}</p>}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">實驗名冊</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="flex flex-wrap gap-2">
            <Button type="button" variant="outline" onClick={() => void handleArchiveLegacy()}>
              封存南勢與蚵間
            </Button>
          </div>
          <Input
            type="file"
            accept=".xlsx"
            onChange={(e) => {
              setRosterFile(e.target.files?.[0] ?? null);
              setDryRun(null);
              setCreatedLogins([]);
            }}
          />
          <div className="flex flex-wrap gap-2">
            <Button type="button" variant="outline" disabled={!rosterFile} onClick={() => void handleDryRun()}>
              乾跑
            </Button>
            <Button type="button" disabled={dryRun?.ok !== true} onClick={() => void handleImport()}>
              確認匯入
            </Button>
            <Button type="button" variant="outline" disabled={createdLogins.length === 0} onClick={printSlips}>
              印發放紙條
            </Button>
          </div>
          {dryRun && (
            <div className="space-y-2 text-sm text-slate-700">
              <p>
                八班學生 {dryRun.students_to_create}、導師 {dryRun.teachers_to_create}、略過 507{" "}
                {dryRun.skipped_507}、已存在 {dryRun.skipped_existing}、衝突 {dryRun.conflicts ?? 0}、錯誤{" "}
                {dryRun.errors ?? 0}
              </p>
              {(dryRun.classes ?? []).length > 0 && (
                <p>
                  {(dryRun.classes ?? [])
                    .map((item) => `${item.code} ${item.study_condition} ${item.students} 人`)
                    .join("、")}
                </p>
              )}
              {(dryRun.conflict_logins ?? []).length > 0 && (
                <p>衝突帳號：{dryRun.conflict_logins?.join("、")}</p>
              )}
              {(dryRun.error_reasons ?? []).length > 0 && (
                <p>
                  錯誤：{dryRun.error_reasons?.join("、")}
                  {(dryRun.error_logins ?? []).length > 0 ? `（${dryRun.error_logins?.join("、")}）` : ""}
                </p>
              )}
            </div>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="flex flex-row items-center justify-between">
          <CardTitle className="text-base">班級列表</CardTitle>
          <label className="flex items-center gap-2 text-sm text-slate-600">
            <input
              type="checkbox"
              checked={includeArchived}
              onChange={(e) => setIncludeArchived(e.target.checked)}
            />
            含封存
          </label>
        </CardHeader>
        <CardContent>
          {loading ? (
            <p className="text-sm text-slate-500">載入中…</p>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>名稱</TableHead>
                  <TableHead>年度</TableHead>
                  <TableHead>代碼</TableHead>
                  <TableHead>組別</TableHead>
                  <TableHead>狀態</TableHead>
                  <TableHead>學生數</TableHead>
                  <TableHead>教師數</TableHead>
                  <TableHead className="text-right">操作</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {classes.map((c) => (
                  <TableRow key={c.id}>
                    <TableCell className="font-medium">{c.name}</TableCell>
                    <TableCell>{c.year}</TableCell>
                    <TableCell>{c.external_code || "—"}</TableCell>
                    <TableCell>{c.study_condition || "—"}</TableCell>
                    <TableCell>{c.archived_at ? "已封存" : "使用中"}</TableCell>
                    <TableCell>{c.student_count}</TableCell>
                    <TableCell>{c.teacher_count}</TableCell>
                    <TableCell className="text-right">
                      {!c.archived_at && (
                        <Button variant="ghost" size="sm" onClick={() => void handleArchive(c)}>
                          封存
                        </Button>
                      )}
                      <Button
                        variant="ghost"
                        size="sm"
                        disabled={c.student_count > 0 || c.teacher_count > 0}
                        onClick={() => void handleDelete(c)}
                        title={
                          c.student_count > 0 || c.teacher_count > 0
                            ? "請先移除班級成員"
                            : "刪除班級"
                        }
                      >
                        <Trash2 className="h-4 w-4 text-red-500" />
                      </Button>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
