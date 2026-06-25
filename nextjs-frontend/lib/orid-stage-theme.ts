export type OridStageKey = "O" | "R" | "I" | "D";

export type StageTheme = {
  shortLabel: string;
  topBorder: string;
  titleColor: string;
  cardBorder: string;
  cardFocus: string;
  hintPanel: string;
  hintTitle: string;
  badgeBg: string;
  statusActive: string;
  btnClass: string;
  inputFocus: string;
};

export const ORID_STAGE_THEME: Record<OridStageKey, StageTheme> = {
  O: {
    shortLabel: "觀察",
    topBorder: "border-t-[#6aaee0]",
    titleColor: "text-[#3d7eb0]",
    cardBorder: "border-amber-100",
    cardFocus: "border-[#6aaee0]/60 ring-2 ring-[#6aaee0]/20",
    hintPanel: "bg-[#eef6fc] border-[#c5dff0]",
    hintTitle: "text-[#3d7eb0]",
    badgeBg: "bg-[#6aaee0]",
    statusActive: "border-[#6aaee0]/50 bg-[#eef6fc] text-[#3d7eb0]",
    btnClass: "kid-btn-feedback-o",
    inputFocus: "focus:border-[#6aaee0] focus:ring-[#6aaee0]/25",
  },
  R: {
    shortLabel: "感受",
    topBorder: "border-t-[#e8a84d]",
    titleColor: "text-[#b8741f]",
    cardBorder: "border-amber-100",
    cardFocus: "border-[#e8a84d]/60 ring-2 ring-[#e8a84d]/20",
    hintPanel: "bg-[#fdf5e8] border-[#f0d9b0]",
    hintTitle: "text-[#b8741f]",
    badgeBg: "bg-[#e8a84d]",
    statusActive: "border-[#e8a84d]/50 bg-[#fdf5e8] text-[#b8741f]",
    btnClass: "kid-btn-feedback-r",
    inputFocus: "focus:border-[#e8a84d] focus:ring-[#e8a84d]/25",
  },
  I: {
    shortLabel: "意義",
    topBorder: "border-t-[#66b88f]",
    titleColor: "text-[#3d8a63]",
    cardBorder: "border-amber-100",
    cardFocus: "border-[#66b88f]/60 ring-2 ring-[#66b88f]/20",
    hintPanel: "bg-[#edf7f1] border-[#c5e6d4]",
    hintTitle: "text-[#3d8a63]",
    badgeBg: "bg-[#66b88f]",
    statusActive: "border-[#66b88f]/50 bg-[#edf7f1] text-[#3d8a63]",
    btnClass: "kid-btn-feedback-i",
    inputFocus: "focus:border-[#66b88f] focus:ring-[#66b88f]/25",
  },
  D: {
    shortLabel: "行動",
    topBorder: "border-t-[#9f88cf]",
    titleColor: "text-[#6f58a8]",
    cardBorder: "border-amber-100",
    cardFocus: "border-[#9f88cf]/60 ring-2 ring-[#9f88cf]/20",
    hintPanel: "bg-[#f3effa] border-[#d8ccef]",
    hintTitle: "text-[#6f58a8]",
    badgeBg: "bg-[#9f88cf]",
    statusActive: "border-[#9f88cf]/50 bg-[#f3effa] text-[#6f58a8]",
    btnClass: "kid-btn-feedback-d",
    inputFocus: "focus:border-[#9f88cf] focus:ring-[#9f88cf]/25",
  },
};

export const STAGE_STATUS_BADGE: Record<
  "not_started" | "drafting" | "feedback" | "passed",
  string
> = {
  not_started: "border-amber-100 bg-white text-amber-900/50",
  drafting: "border-amber-200 bg-amber-50 text-amber-900",
  feedback: "border-amber-200 bg-[#fdf5e8] text-amber-900",
  passed: "border-emerald-300 bg-emerald-50 text-emerald-800",
};
