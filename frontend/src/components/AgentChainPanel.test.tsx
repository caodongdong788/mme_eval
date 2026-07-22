import { cleanup, fireEvent, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { renderWithProviders } from "../test/renderWithProviders";
import { AgentChainPanel } from "./AgentChainPanel";

const sources = [
  { key: "medical_records", label: "病例夹", status: "read" as const, summary: "读取 1 份病例资料（2 个附件）", calls: 1, count: 1, details: ["术后病理"] },
  { key: "medical_metrics", label: "报告指标", status: "hit" as const, summary: "命中病历夹结构化指标", calls: 1, count: 0, details: [] },
  { key: "timeline", label: "健康 Timeline", status: "unused" as const, summary: "本轮未调用", calls: 0, count: 0, details: [] },
  { key: "chat_history", label: "历史对话", status: "hit" as const, summary: "检索历史对话并返回结果", calls: 1, count: 0, details: [] },
  {
    key: "literature_rag",
    label: "医学文献 RAG",
    status: "hit" as const,
    summary: "检索 25 条，采用 2 条",
    calls: 1,
    count: 0,
    query: "他莫昔芬漏服",
    details: ["药品说明书", "临床研究"],
    metrics: { searched: 25, qualified: 17, candidates: 17, selected: 2, threshold: 0.65 },
  },
  { key: "current_report", label: "当前报告", status: "unused" as const, summary: "本轮未调用", calls: 0, count: 0, details: [] },
];

afterEach(cleanup);

describe("AgentChainPanel", () => {
  it("renders distilled sources, risks, actions and chain quality", () => {
    const onSync = vi.fn();
    renderWithProviders(
      <AgentChainPanel
        onSync={onSync}
        caseInitialState={{
          user_profile: { "治疗阶段": "产后恢复期", "用药-他莫昔芬": "计划恢复服用" },
          timeline: [{ "他莫昔芬（key=tamoxifen；用药）": "2026-07-20：医生提示产后 5 天不宜立即启动" }],
        }}
        trace={{
          evaluation_identity: {
            test_user_id: "00000000-0000-0000-0000-000000000101",
            verification_code: "731904",
            cx_session_id: "948c4c16-75d9-4597-8980-3757fe68110c",
            reset_status: "success",
            user_profile: { nickname: "小橙", treatment_stage: "术后康复" },
          },
          langfuse_trace_ids: ["trace-1"],
          agent_chain: {
            status: "synced",
            trace_ids: ["trace-1"],
            traces: [{ trace_id: "trace-1", trace_url: "https://lf.example/trace-1" }],
            nodes: [{ id: "agent", type: "AGENT", name: "cx.agent.chat.test" }],
            summary: {
              steps: [
                { id: "agent", title: "Agent 接收请求", category: "agent", summary: "加载上下文并编排本轮任务", duration_ms: 18327, status: "success" },
                { id: "rag", title: "医学文献 RAG", category: "source", summary: "他莫昔芬漏服", duration_ms: 2300, status: "success" },
              ],
              sources,
              risks: [{ level: "B0", category: "当前症状", symptom: "术侧上肢肿胀", reason: "需排除血栓", status: "success" }],
              actions: [{ tool: "update_structured_profile", label: "更新用户画像", summary: "自动更新 1 项，待确认 0 项", status: "success" }],
              quality: {
                total_duration_ms: 18327,
                model_calls: 2,
                tool_calls: 4,
                tool_successes: 4,
                tool_failures: 0,
                models: ["kimi-k2.5"],
                providers: ["dashscope"],
                input_tokens: 1000,
                cached_tokens: 3000,
                output_tokens: 500,
                total_tokens: 4500,
                cache_hit_rate: 0.75,
                retry_count: 2,
                anomalies: ["工具协议文本泄漏"],
                errors: [],
              },
            },
          },
        }}
      />,
    );

    expect(screen.getByText("已清空")).toBeInTheDocument();
    expect(screen.getByText("登录账号")).toBeInTheDocument();
    expect(screen.getByText("+8610000000101")).toBeInTheDocument();
    expect(screen.getByText("验证码")).toBeInTheDocument();
    expect(screen.getByText("731904")).toBeInTheDocument();
    expect(screen.queryByText("00000000-0000-0000-0000-000000000101")).not.toBeInTheDocument();
    expect(screen.getByText("948c4c16-75d9-4597-8980-3757fe68110c")).toBeInTheDocument();
    expect(screen.getByText("用户档案和过往事实")).toBeInTheDocument();
    expect(screen.getAllByText("用户档案").length).toBeGreaterThanOrEqual(2);
    expect(screen.getAllByText("过往事实").length).toBeGreaterThanOrEqual(2);
    expect(screen.getAllByText("已注入").length).toBeGreaterThanOrEqual(2);
    expect(screen.getByText("调用路径")).toBeInTheDocument();
    expect(screen.getByText("信息来源")).toBeInTheDocument();
    expect(screen.getByText("读取 1 份病例资料（2 个附件）")).toBeInTheDocument();
    expect(screen.getByText("他莫昔芬漏服")).toBeInTheDocument();
    expect(screen.getByText("25 → 17 → 17 → 2")).toBeInTheDocument();
    expect(screen.getByText("风险 B0")).toBeInTheDocument();
    expect(screen.getByText("更新用户画像")).toBeInTheDocument();
    expect(screen.getByText("工具协议文本泄漏")).toBeInTheDocument();
    expect(screen.getByText("75%")).toBeInTheDocument();
    expect(screen.queryByText(/原始 Langfuse 数据/)).not.toBeInTheDocument();
    expect(screen.queryByText(/在 Langfuse 查看第/)).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "查看详情" }));
    expect(screen.getAllByText("他莫昔芬（key=tamoxifen；用药）").length).toBeGreaterThanOrEqual(2);
    expect(screen.getByText("2026-07-20：医生提示产后 5 天不宜立即启动")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /重新同步/ }));
    expect(onSync).toHaveBeenCalledOnce();
  });

  it("does not render a user profile section when the profile is empty", () => {
    renderWithProviders(
      <AgentChainPanel
        onSync={vi.fn()}
        trace={{
          langfuse_trace_ids: ["trace-2"],
          agent_chain: {
            status: "synced",
            trace_ids: ["trace-2"],
            nodes: [],
            summary: {
              steps: [],
              sources,
              risks: [],
              actions: [],
              quality: {
                model_calls: 0,
                tool_calls: 0,
                tool_successes: 0,
                tool_failures: 0,
                models: [],
                providers: [],
                input_tokens: 0,
                cached_tokens: 0,
                output_tokens: 0,
                total_tokens: 0,
                retry_count: 0,
                anomalies: [],
                errors: [],
              },
            },
          },
        }}
      />,
    );

    expect(screen.queryByText("用户画像")).not.toBeInTheDocument();
    expect(screen.getByText("Trace 中暂无 observation")).toBeInTheDocument();
  });
});
