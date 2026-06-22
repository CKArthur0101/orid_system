export type MissionStageKey = "O" | "R" | "I" | "D";

export type MissionMeta = {
  oridTitle: string;
  missionTitle: string;
  helperHint: string;
  submitEncouragement: string;
};

export const STAGE_MISSION_META: Record<MissionStageKey, MissionMeta> = {
  O: {
    oridTitle: "O 客觀事實",
    missionTitle: "任務 1｜找出故事發生了什麼",
    helperHint: "先想想故事中「誰」做了「什麼事」。",
    submitEncouragement: "你完成了故事事實任務！",
  },
  R: {
    oridTitle: "R 感受原因",
    missionTitle: "任務 2｜說出你的感受",
    helperHint: "現在想想，你看到這件事時有什麼感覺？",
    submitEncouragement: "你成功寫出自己的感受了！",
  },
  I: {
    oridTitle: "I 意義推論",
    missionTitle: "任務 3｜發現故事想告訴你的事",
    helperHint: "這個故事想告訴我們什麼呢？",
    submitEncouragement: "你找到故事中的重要啟發了！",
  },
  D: {
    oridTitle: "D 行動決策",
    missionTitle: "任務 4｜想一個你可以做到的行動",
    helperHint: "如果換成你，下次可以怎麼做？",
    submitEncouragement: "你想出一個可以做到的行動了！",
  },
};

export const DRAFT_SAVE_ENCOURAGEMENT = "已幫你保存想法囉！";
export const SUBMIT_PARTIAL_ENCOURAGEMENT = "已幫你保存今天的寫作囉！";
export const SUBMIT_ALL_DONE_ENCOURAGEMENT = "太棒了！你完成今天的 ORID 反思任務！";
