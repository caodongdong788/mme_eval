import { screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import type { OnlineEvalCase } from "../api/index";
import { renderWithProviders } from "../test/renderWithProviders";
import { OnlineEvalConversation } from "./OnlineEvalConversation";

const baseCase: OnlineEvalCase = {
  id: 1,
  external_id: "online_case_1",
  case_name: "含图多轮对话",
  user_text: "压平用户",
  assistant_text: "压平回复",
  user_profile: "年龄：36\n治疗阶段：内分泌治疗中",
  raw_messages: [
    { role: "user", content: "第一问" },
    { role: "assistant", content: "第一答" },
    {
      role: "user",
      content: "第二问",
      rich_text: [
        { type: "text", text: "第二问" },
        {
          type: "embed-image",
          image_token: "Rhb9bkUUfoA7rSxq4YzcVTT8nAs",
          image_width: 1200,
          image_height: 1600,
        },
      ],
    },
    { role: "assistant", content: "第二答" },
  ],
  task_type: "report_interpretation",
  gate_status: "pass",
  total_score: 8.5,
  grade: "good",
  dimension_scores: {},
  dimension_feedback: {},
  risk_tags: [],
  evidence: [],
  improvement_suggestions: [],
  benchmark_candidate: false,
};

describe("OnlineEvalConversation", () => {
  it("renders raw multi-turn messages and Feishu images", () => {
    renderWithProviders(<OnlineEvalConversation row={baseCase} />);

    expect(screen.getByText("第 1 轮")).toBeInTheDocument();
    expect(screen.getByText("第 2 轮")).toBeInTheDocument();
    expect(screen.getByText("第一问")).toBeInTheDocument();
    expect(screen.getByText("第一答")).toBeInTheDocument();
    expect(screen.getByText("用户档案")).toBeInTheDocument();
    expect(screen.getByText("治疗阶段")).toBeInTheDocument();
    expect(screen.getByText("内分泌治疗中")).toBeInTheDocument();
    expect(screen.getByText("第二答")).toBeInTheDocument();
    expect(screen.queryByText("压平用户")).not.toBeInTheDocument();

    expect(screen.getByTestId("online-case-image")).toHaveAttribute(
      "src",
      "/api/benchmarks/feishu-images/Rhb9bkUUfoA7rSxq4YzcVTT8nAs"
    );
  });
});
