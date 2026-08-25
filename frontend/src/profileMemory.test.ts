import { describe, expect, it } from "vitest";
import { formatProfileMemoryEntry, parseProfileMemoryEntry } from "./profileMemory";

describe("profile memory entries", () => {
  it("splits a standard USER.md category from its content", () => {
    expect(parseProfileMemoryEntry("[沟通] 偏好先给结论，再列数据")).toEqual({
      category: "沟通",
      content: "偏好先给结论，再列数据",
    });
  });

  it("maps the legacy psychological category to concern", () => {
    expect(parseProfileMemoryEntry("[心理] 对复查指标变化容易焦虑")).toEqual({
      category: "关注",
      content: "对复查指标变化容易焦虑",
    });
  });

  it("keeps unknown legacy text intact instead of dropping it", () => {
    expect(parseProfileMemoryEntry("[自定义] 保留历史内容")).toEqual({
      content: "[自定义] 保留历史内容",
    });
  });

  it("serializes the visual fields back to the compatible YAML string", () => {
    expect(formatProfileMemoryEntry("背景", "家属协助记录复查安排")).toBe("[背景] 家属协助记录复查安排");
  });
});
