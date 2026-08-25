import { describe, expect, it } from "vitest";
import { accountInitializationModules, findConversationContextReferences } from "../utils/conversationContext";

describe("findConversationContextReferences", () => {
  it("reports only profile and timeline facts that are quoted by an assistant reply", () => {
    const references = findConversationContextReferences(
      {
        user_profile: {
          "用药-他莫昔芬": "计划尽快恢复服用，医生提示产后5天不宜立即启动",
          "症状-湿疹": "持续瘙痒，影响睡眠",
        },
        timeline: [
          { "他莫昔芬（key=tamoxifen；用药）": "2026-07-20：医生提示产后5天不宜立即启动；伤口正常无异常" },
          { "湿疹（key=eczema；症状）": "2026-07-12：持续瘙痒，影响睡眠" },
        ],
      },
      [
        { role: "user", content: "多久恢复吃药" },
        { role: "assistant", content: "我之前记录到医生提示过产后5天不宜立即启动，且你说伤口正常无异常。" },
      ],
    );

    expect(references.map((item) => item.label)).toEqual([
      "用药-他莫昔芬",
      "他莫昔芬（key=tamoxifen；用药）",
    ]);
    expect(references.every((item) => item.turns[0] === 1)).toBe(true);
    expect(references.every((item) => item.evidence === "产后5天不宜立即启动")).toBe(true);
  });

  it("matches a short wording variation without requiring an exact sentence", () => {
    const references = findConversationContextReferences(
      { user_profile: { 用药计划: "计划尽快恢复服用" } },
      [{ role: "assistant", content: "你可以先和医生确认，再尽快恢复吃药。" }],
    );

    expect(references).toHaveLength(1);
    expect(references[0]).toMatchObject({ label: "用药计划", evidence: "尽快恢复" });
  });
});

describe("accountInitializationModules", () => {
  it("shows every configured account-initialization module and skips empty modules", () => {
    const modules = accountInitializationModules({
      user_profile: { 当前用药: "tamoxifen" },
      timeline: [{ 复诊: "2026-07-04 复查" }],
      profile_memory: ["[沟通] 偏好先给结论"],
      response_preferences: [{ preference: "先给结论", basis: "用户明确表达" }],
      medical_documents: [{ title: "复查血液指标", document_date: "2026-07-04", metrics: [{ name: "CA15-3", value: 16, unit: "U/mL" }] }],
      chat_history: [{ title: "上次复查咨询", messages: [{ role: "user", content: "CA15-3 是多少" }, { role: "assistant", content: "本次为 16" }] }],
      tool_state: {
        scheduled_tasks: [{ task_name: "复查提醒", due_at: "2026-09-01", message: "复查血常规" }],
        check_ins: [{ title: "今日体温", recorded_at: "2026-08-20", values: { temperature: 36.6 } }],
        undercurrent_tasks: [{ ref: "task_1", kind: "follow_up", status: "pending" }],
      },
    });

    expect(modules.map((module) => module.label)).toEqual([
      "用户档案",
      "过往事实",
      "长期画像记忆",
      "回复偏好",
      "病例夹",
      "历史对话",
      "提醒任务",
      "打卡记录",
      "暗流任务",
    ]);
    expect(modules.find((module) => module.key === "medical_documents")?.entries[0].content).toContain("CA15-3：16 U/mL");
    expect(modules.find((module) => module.key === "chat_history")?.entries[0].content).toContain("Agent：本次为 16");
  });
});
