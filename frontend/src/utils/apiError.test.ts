import { describe, expect, it } from "vitest";
import { formatApiError, humanizeErrorText } from "./apiError";

describe("apiError 中文错误说明", () => {
  it("把空维度要求的 Pydantic 原文翻译成具体中文", () => {
    const text = humanizeErrorText(
      "1 validation error for TestCase evaluation.dimension_criteria.plan_feasibility.criteria List should have at least 1 item after validation, not 0 [type=too_short]",
    );
    expect(text).toContain("方案可行性与依从引导");
    expect(text).toContain("至少需要保留 1 条");
    expect(text).not.toContain("validation error");
  });

  it("把 FastAPI 结构化校验错误翻译为中文字段", () => {
    const text = formatApiError({
      response: {
        status: 422,
        data: {
          detail: [
            {
              loc: ["body", "evaluation", "dimension_criteria", "medical_safety", "criteria"],
              msg: "List should have at least 1 item after validation, not 0",
              type: "too_short",
              ctx: { min_length: 1 },
            },
          ],
        },
      },
    });
    expect(text).toBe(
      "请求参数校验失败：医学安全性的“评测要求”至少需要保留 1 条；如果该维度没有补充要求，请删除整个空维度",
    );
  });

  it("不向用户展示未知英文异常", () => {
    expect(humanizeErrorText("Something unexpected happened", "保存失败")).toBe("保存失败");
  });

  it("翻译常见上游服务错误", () => {
    expect(humanizeErrorText("502 Bad Gateway")).toBe("上游服务暂时不可用，请稍后重试");
  });

  it("隐藏模型服务的英文内部异常", () => {
    expect(
      humanizeErrorText("AI 归因生成失败：InternalServerError: An internal error has occurred"),
    ).toBe("模型服务内部处理失败，请稍后重试；如持续出现，请更换模型或检查模型配置");
  });

  it("保留 409 返回的具体中文原因", () => {
    expect(
      formatApiError({
        response: {
          status: 409,
          data: { detail: "评测名称「账号初始化与断言示例」已存在，请换一个名称" },
        },
      }),
    ).toBe("评测名称「账号初始化与断言示例」已存在，请换一个名称");
  });

  it("没有具体原因的 409 使用可理解的兜底提示", () => {
    expect(humanizeErrorText("Conflict", "操作失败", 409)).toBe(
      "当前操作暂时无法完成，相关内容可能已被更新；请刷新页面后重试",
    );
  });
});
