"use client";

export default function LoginError({
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <div className="orid-forest-page flex min-h-screen items-center justify-center px-4">
      <div className="kid-shell max-w-md space-y-4 p-6 text-center">
        <h1 className="text-lg font-bold text-amber-950">登入頁面載入失敗</h1>
        <p className="text-sm leading-relaxed text-amber-900/80">
          若畫面一片空白，常見原因是瀏覽器翻譯外掛（例如 Immersive Translate）干擾了頁面。
          請先關閉翻譯外掛，或使用無痕視窗再開一次。
        </p>
        <button type="button" className="kid-btn-primary w-full" onClick={() => reset()}>
          重新載入
        </button>
      </div>
    </div>
  );
}
