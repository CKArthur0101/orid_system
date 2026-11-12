"use client";

import { useEffect, useState } from "react";
import { createPortal } from "react-dom";
import { Eye, EyeOff, KeyRound } from "lucide-react";

type PasswordStatus = {
  eligible: boolean;
  locked: boolean;
};

const PASSWORD_HINT = "請只用英文字母和數字喔";
const LETTERS_DIGITS = /^[A-Za-z0-9]+$/;

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

function PasswordInput({
  id,
  label,
  value,
  onChange,
  enterKeyHint,
  autoFocus,
}: {
  id: string;
  label: string;
  value: string;
  onChange: (value: string) => void;
  enterKeyHint?: "next" | "done";
  autoFocus?: boolean;
}) {
  const [visible, setVisible] = useState(false);

  return (
    <div className="mt-3 first:mt-4">
      <label className="block text-sm font-medium text-amber-950" htmlFor={id}>
        {label}
      </label>
      <div className="relative mt-1">
        <input
          id={id}
          type={visible ? "text" : "password"}
          value={value}
          onChange={(event) => onChange(event.target.value)}
          className="w-full rounded-xl border border-amber-200 px-3 py-2 pr-11 text-base text-amber-950"
          autoComplete="new-password"
          enterKeyHint={enterKeyHint}
          autoFocus={autoFocus}
          spellCheck={false}
          inputMode="text"
        />
        <button
          type="button"
          className="absolute inset-y-0 right-0 flex w-11 items-center justify-center text-amber-800/70 hover:text-amber-950"
          aria-label={visible ? "隱藏密碼" : "顯示密碼"}
          aria-pressed={visible}
          onClick={() => setVisible((current) => !current)}
        >
          {visible ? <EyeOff className="h-5 w-5" aria-hidden /> : <Eye className="h-5 w-5" aria-hidden />}
        </button>
      </div>
    </div>
  );
}

export function StudentPasswordButton() {
  const [status, setStatus] = useState<PasswordStatus | null>(null);
  const [open, setOpen] = useState(false);
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [done, setDone] = useState(false);
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
  }, []);

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

  useEffect(() => {
    if (!open) return;
    const previous = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = previous;
    };
  }, [open]);

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
    if (!LETTERS_DIGITS.test(next)) {
      setError(PASSWORD_HINT);
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

  const dialog =
    open && mounted
      ? createPortal(
          <div
            className="fixed inset-0 z-[100] overflow-y-auto overscroll-contain bg-amber-950/45"
            role="dialog"
            aria-modal="true"
            aria-labelledby="student-password-title"
          >
            <div className="flex min-h-[100dvh] items-center justify-center px-4 py-10 sm:py-12">
              <form
                onSubmit={(event) => void submit(event)}
                className="my-auto w-full max-w-sm rounded-2xl border border-amber-200 bg-[#fffcf7] p-5 shadow-2xl"
              >
                <h2 id="student-password-title" className="text-lg font-bold text-amber-950">
                  修改密碼
                </h2>
                <p className="mt-1 text-sm leading-relaxed text-amber-900/70">
                  只能修改一次。改完這個按鈕會鎖住，忘記密碼時可以問老師。
                </p>
                <p className="mt-2 text-sm font-medium text-amber-900/80">{PASSWORD_HINT}</p>
                <PasswordInput
                  id="new-password"
                  label="新密碼"
                  value={password}
                  onChange={setPassword}
                  enterKeyHint="next"
                  autoFocus
                />
                <PasswordInput
                  id="confirm-password"
                  label="再輸入一次"
                  value={confirm}
                  onChange={setConfirm}
                  enterKeyHint="done"
                />
                {error ? <p className="mt-3 text-sm text-red-600">{error}</p> : null}
                <div className="mt-5 flex justify-end gap-2">
                  <button
                    type="button"
                    onClick={close}
                    className="kid-btn-3d-secondary !min-h-[44px] !px-3 !text-sm"
                  >
                    取消
                  </button>
                  <button
                    type="submit"
                    disabled={saving}
                    className="kid-btn-3d-primary !min-h-[44px] !px-3 !text-sm"
                  >
                    {saving ? "儲存中…" : "確定修改"}
                  </button>
                </div>
              </form>
            </div>
          </div>,
          document.body,
        )
      : null;

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
      {dialog}
    </>
  );
}
