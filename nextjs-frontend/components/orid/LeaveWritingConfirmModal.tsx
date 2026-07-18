"use client";

type LeaveIntent = "home" | "logout";

export function LeaveWritingConfirmModal({
  intent,
  onStay,
  onLeave,
}: {
  intent: LeaveIntent;
  onStay: () => void;
  onLeave: () => void;
}) {
  const leaveLabel = intent === "logout" ? "直接登出" : "直接回首頁";

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/45 p-4"
      role="dialog"
      aria-modal="true"
      aria-labelledby="leave-writing-title"
      onClick={onStay}
    >
      <div
        className="w-full max-w-[min(92vw,22rem)] rounded-2xl border-2 border-amber-200 bg-[#fffcf7] p-5 shadow-xl md:p-6"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="text-center text-2xl" aria-hidden>
          🌰
        </div>
        <h2
          id="leave-writing-title"
          className="mt-2 text-center text-base font-bold text-amber-950 md:text-lg"
        >
          離開前先確認一下
        </h2>
        <p className="mt-2 text-center text-sm leading-relaxed text-amber-900/80">
          離開寫作畫面之前，記得先按下方的
          <span className="font-semibold text-amber-950">「儲存我的寫作」</span>
          ，才不會弄丟你寫好的內容喔！
        </p>

        <div className="mt-5 flex flex-col gap-2">
          <button
            type="button"
            onClick={onStay}
            className="min-h-[44px] w-full rounded-xl bg-gradient-to-r from-amber-700 to-orange-800 px-4 py-2.5 text-sm font-semibold text-white shadow-sm transition hover:from-amber-600 hover:to-orange-700"
          >
            先去儲存
          </button>
          <button
            type="button"
            onClick={onLeave}
            className="min-h-[44px] w-full rounded-xl border-2 border-amber-200 bg-white px-4 py-2.5 text-sm font-semibold text-amber-900/80 transition hover:bg-amber-50"
          >
            {leaveLabel}
          </button>
        </div>
      </div>
    </div>
  );
}
