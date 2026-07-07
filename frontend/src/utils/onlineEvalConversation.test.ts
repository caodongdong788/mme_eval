import { describe, expect, it } from "vitest";
import {
  buildOnlineEvalConversationRounds,
  normaliseOnlineEvalMessages,
} from "./onlineEvalConversation";

describe("onlineEvalConversation", () => {
  it("keeps raw multi-turn messages in round order", () => {
    const rounds = buildOnlineEvalConversationRounds({
      raw_messages: [
        { role: "user", content: "第一问" },
        { role: "assistant", content: "第一答" },
        { role: "user", content: "第二问 [图片：image_token=IMG2]" },
        { role: "assistant", content: "第二答" },
      ],
      user_text: "压平用户",
      assistant_text: "压平回复",
    });

    expect(rounds).toEqual([
      { user: "第一问", assistant: "第一答", extras: [] },
      { user: "第二问 [图片：image_token=IMG2]", assistant: "第二答", extras: [] },
    ]);
  });

  it("falls back to flattened texts when raw messages are absent", () => {
    expect(
      normaliseOnlineEvalMessages({
        raw_messages: [],
        user_text: "用户原文",
        assistant_text: "Bot 回复",
      })
    ).toEqual([
      { role: "user", content: "用户原文" },
      { role: "assistant", content: "Bot 回复" },
    ]);
  });

  it("preserves rich_text nodes for detail rendering", () => {
    const richText = [
      { type: "text", text: "第二问" },
      { type: "embed-image", image_token: "IMG2", image_width: 1200, image_height: 1600 },
    ];

    const rounds = buildOnlineEvalConversationRounds({
      raw_messages: [
        { role: "user", content: "第二问 [图片：image_token=IMG2]", rich_text: richText },
        { role: "assistant", content: "第二答", rich_text: [{ type: "text", text: "第二答" }] },
      ],
    });

    expect(rounds[0].userRichText).toEqual(richText);
    expect(rounds[0].assistantRichText).toEqual([{ type: "text", text: "第二答" }]);
  });
});
