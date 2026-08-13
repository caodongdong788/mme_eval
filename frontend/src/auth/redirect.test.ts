import { describe, expect, it } from "vitest";
import { feishuLoginPath, loginPath, sanitizeReturnTo } from "./redirect";

describe("auth redirect", () => {
  it("preserves a run detail path, query and hash", () => {
    const target = "/runs/26?view=detail#case_11";
    expect(sanitizeReturnTo(target)).toBe(target);
    expect(loginPath(target)).toBe(
      "/login?redirect_to=%2Fruns%2F26%3Fview%3Ddetail%23case_11"
    );
    expect(feishuLoginPath(target)).toBe(
      "/api/auth/feishu/login?redirect_to=%2Fruns%2F26%3Fview%3Ddetail%23case_11"
    );
  });

  it.each([
    "https://evil.example/runs/26",
    "//evil.example/runs/26",
    "/\\evil.example/runs/26",
    "/login",
  ])("rejects unsafe return target %s", (target) => {
    expect(sanitizeReturnTo(target)).toBe("/runs");
  });
});
