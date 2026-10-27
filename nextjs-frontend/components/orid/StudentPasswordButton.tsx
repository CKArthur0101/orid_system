"use client";

import { useEffect, useState } from "react";
import { KeyRound } from "lucide-react";

type PasswordStatus = {
  eligible: boolean;
  locked: boolean;
};

async function readDetail(response: Response): Promise<string> {
  const text = await response.text();
  try {
    const data = JSON.parse(text) as { detail?: unknown };
    if (typeof data.detail === "string" && data.detail.trim()) return data.detail;
  } catch {
    // The response was not JSON.
  }
  return "修改失敗，請再試一次。";
}

export function StudentPasswordButton() {
  const [status, setStatus] = useState<PasswordStatus | null>(null);
  const [open, setOpen] = useState(false);
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [done, setDone] = useState(false);

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      try {
        const response = await fetch("/api/users/me/password-change", { cache: "no-store" });
        if (!response.ok || cancelled) return;
        const data = (await response.json()) as PasswordStatus;
        if (!cancelled) setStatus(data);
      } catch {
        // The name bar still works if this status request fails.
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  if (!status?.eligible) return null;

  function close() {
    if (saving) return;
    setOpen(false);
    setPassword("");
    setConfirm("");
    setError(null);
  }

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    const next = password.trim();
    if (!next) {
      setError("請輸入密碼。");
      return;
    }
    if (next !== confirm.trim()) {
      setError("兩次密碼不一樣。");
      return;
    }
    setSaving(true);
    setError(null);
    try {
      const response = await fetch("/api/users/me/password-change", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ password: next }),
      });
      if (!response.ok) throw new Error(await readDetail(response));
      setStatus({ eligible: true, locked: true });
      setDone(true);
      setOpen(false);
      setPassword("");
      setConfirm("");
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "修改失敗，請再試一次。");
    } finally {
      setSaving(false);
    }
  }

  return (
    <>
      <button
        type="button"
        disabled={status.locked}
        onClick={() => {
          setDone(false);
          setOpen(true);
        }}
        className="kid-btn-3d-secondary !min-h-[36px] !gap-1.5 !px-3 !py-1.5 !text-sm disabled:cursor-not-allowed disabled:opacity-60"
      >
        <KeyRound className="h-4 w-4" />
        <span className="hidden sm:inline">{status.locked ? "已修改密碼" : "修改密碼"}</span>
      </button>
      {done ? <span className="sr-only">密碼已修改，之後請用新密碼登入。</span> : null}
      {open ? (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-amber-950/30 px-4">
          <form
            onSubmit={(event) => void submit(event)}
            className="w-full max-w-sm rounded-2xl border border-amber-200 bg-[#fffcf7] p-5 shadow-lg"
          >
            <h2 className="text-lg font-bold text-amber-950">修改密碼</h2>
            <p className="mt-1 text-sm leading-relaxed text-amber-900/70">
              只能修改一次。改完這個按鈕會鎖住，忘記密碼時可以問老師。
            </p>
            <label className="mt-4 block text-sm font-medium text-amber-950" htmlFor="new-password">
              新密碼
            </label>
            <input
              id="new-password"
              type="password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              className="mt-1 w-full rounded-xl border border-amber-200 px-3 py-2 text-amber-950"
              autoComplete="new-password"
            />
            <label className="mt-3 block text-sm font-medium text-amber-950" htmlFor="confirm-password">
              再輸入一次
            </label>
            <input
              id="confirm-password"
              type="password"
              value={confirm}
              onChange={(event) => setConfirm(event.target.value)}
              className="mt-1 w-full rounded-xl border border-amber-200 px-3 py-2 text-amber-950"
              autoComplete="new-password"
            />
            {error ? <p className="mt-3 text-sm text-red-600">{error}</p> : null}
            <div className="mt-5 flex justify-end gap-2">
              <button type="button" onClick={close} className="kid-btn-3d-secondary !min-h-[36px] !px-3 !text-sm">
                取消
              </button>
              <button type="submit" disabled={saving} className="kid-btn-3d-primary !min-h-[36px] !px-3 !text-sm">
                {saving ? "儲存中…" : "確定修改"}
              </button>
            </div>
          </form>
        </div>
      ) : null}
    </>
  );
}
