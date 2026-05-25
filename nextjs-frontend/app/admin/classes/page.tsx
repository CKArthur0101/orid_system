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
  student_count: number;
  teacher_count: number;
};

export default function AdminClassesPage() {
  const [classes, setClasses] = useState<AdminClass[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [name, setName] = useState("");
  const [externalCode, setExternalCode] = useState("");
  const [saving, setSaving] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const r = await fetch("/api/admin/classes", { cache: "no-store" });
      if (!r.ok) throw new Error(await r.text());
      setClasses(await r.json());
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "載入失敗");
    } finally {
      setLoading(false);
    }
  }, []);

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
                placeholder="例如：蚵間國小"
                required
              />
            </div>
            <div className="space-y-1 flex-1">
              <Label htmlFor="class-code">外部代碼（選填）</Label>
              <Input
                id="class-code"
                value={externalCode}
                onChange={(e) => setExternalCode(e.target.value)}
                placeholder="例如：kejian-guo-xiao"
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
          <CardTitle className="text-base">班級列表</CardTitle>
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
                    <TableCell>{c.student_count}</TableCell>
                    <TableCell>{c.teacher_count}</TableCell>
                    <TableCell className="text-right">
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
