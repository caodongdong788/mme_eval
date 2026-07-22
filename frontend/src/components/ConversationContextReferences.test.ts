import { describe, expect, it } from "vitest";
import { findConversationContextReferences } from "./ConversationContextReferences";

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
