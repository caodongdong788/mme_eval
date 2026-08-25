import { cleanup, fireEvent, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { renderWithProviders } from "../test/renderWithProviders";
import { AgentChainPanel } from "./AgentChainPanel";

const sources = [
  { key: "medical_records", label: "病例夹", status: "read" as const, summary: "读取 1 份病例资料（2 个附件）", calls: 1, count: 1, details: ["术后病理"] },
  { key: "medical_metrics", label: "报告指标", status: "hit" as const, summary: "命中病历夹结构化指标", calls: 1, count: 0, details: [] },
  { key: "timeline", label: "过往事实", status: "unused" as const, summary: "本轮未调用", calls: 0, count: 0, details: [] },
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
          response_preferences: [{ preference: "先给结论，再说明数据依据" }],
        }}
        trace={{
          evaluation_identity: {
            test_user_id: "00000000-0000-0000-0000-000000000101",
            verification_code: "731904",
            cx_session_id: "948c4c16-75d9-4597-8980-3757fe68110c",
            reset_status: "success",
            user_profile: { nickname: "小橙", treatment_stage: "术后康复" },
            system_prompt_enabled: true,
            response_preference: {
              status: "success",
              configuredCount: 1,
              loaded: true,
              effective: true,
            },
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
    expect(screen.getAllByText("初始化成功").length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText("登录账号")).toBeInTheDocument();
    expect(screen.getByText("+8610000000101")).toBeInTheDocument();
    expect(screen.getByText("验证码")).toBeInTheDocument();
    expect(screen.getByText("731904")).toBeInTheDocument();
    expect(screen.queryByText("00000000-0000-0000-0000-000000000101")).not.toBeInTheDocument();
    expect(screen.getByText("948c4c16-75d9-4597-8980-3757fe68110c")).toBeInTheDocument();
    expect(screen.getByText("账号初始化数据")).toBeInTheDocument();
    expect(screen.getAllByText("用户档案").length).toBeGreaterThanOrEqual(2);
    expect(screen.getAllByText("过往事实").length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText("已注入").length).toBeGreaterThanOrEqual(2);
    expect(screen.getByText("调用路径")).toBeInTheDocument();
    expect(screen.getByText("信息来源与运行验收")).toBeInTheDocument();
    expect(screen.getByText("读取 1 份病例资料（2 个附件）")).toBeInTheDocument();
    expect(screen.getByText("他莫昔芬漏服")).toBeInTheDocument();
    expect(screen.getByText("25 → 17 → 17 → 2")).toBeInTheDocument();
    expect(screen.getByText("风险 B0")).toBeInTheDocument();
    expect(screen.getByText("更新用户画像")).toBeInTheDocument();
    expect(screen.getByText("工具协议文本泄漏")).toBeInTheDocument();
    expect(screen.getByText("75%")).toBeInTheDocument();
    expect(screen.queryByText(/原始 Langfuse 数据/)).not.toBeInTheDocument();
    expect(screen.queryByText(/在 Langfuse 查看第/)).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "查看完整数据" }));
    expect(screen.getAllByText("他莫昔芬（key=tamoxifen；用药）").length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText("2026-07-20：医生提示产后 5 天不宜立即启动")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /重新同步/ }));
    expect(onSync).toHaveBeenCalledOnce();
  });

  it("renders a compact chain summary without raw Langfuse nodes", () => {
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
    expect(screen.getByText("调用路径")).toBeInTheDocument();
    expect(screen.queryByText("Trace 中暂无 observation")).not.toBeInTheDocument();
  });

  it("shows response preferences as ineffective when the system prompt is disabled", () => {
    renderWithProviders(
      <AgentChainPanel
        onSync={vi.fn()}
        caseInitialState={{
          response_preferences: [{ preference: "先给结论，再说明数据依据" }],
        }}
        trace={{
          evaluation_identity: {
            system_prompt_enabled: false,
            response_preference: {
              status: "inactive_system_prompt",
              configuredCount: 1,
              loaded: true,
              effective: false,
            },
          },
        }}
      />,
    );

    expect(screen.getByText("未生效（系统提示词关闭）")).toBeInTheDocument();
  });

  it("merges assertion outcomes into the information source module", () => {
    renderWithProviders(
      <AgentChainPanel
        onSync={vi.fn()}
        assertions={[
          { id: "rag_hit", type: "retrieval", description: "医学文献检索至少采用一条证据", name: "literature_rag", min_count: 1 },
          { id: "read_metrics", type: "tool_call", description: "必须读取结构化病例指标", name: "read_medical_metrics", min_count: 1 },
          { id: "mention_metric", type: "transcript", description: "最终回答应提及 CA15-3", contains: "CA15-3", dimensions: ["professional_accuracy"], deduction: 1 },
        ]}
        assertionVerdicts={[
          { name: "assertion.rag_hit", passed: false, reason: "断言未满足：医学文献检索至少采用一条证据", details: { type: "retrieval", status: "fail", count: 0, min_count: 1 } },
          { name: "assertion.read_metrics", passed: true, details: { type: "tool_call", status: "pass", count: 1, min_count: 1 } },
          { name: "assertion.mention_metric", passed: false, reason: "断言未满足：最终回答应提及 CA15-3", details: { type: "transcript", status: "fail" } },
        ]}
        trace={{
          langfuse_trace_ids: ["trace-3"],
          agent_chain: {
            status: "synced",
            trace_ids: ["trace-3"],
            summary: {
              steps: [],
              sources,
              risks: [],
              actions: [],
              quality: {
                model_calls: 0, tool_calls: 1, tool_successes: 1, tool_failures: 0,
                models: [], providers: [], input_tokens: 0, cached_tokens: 0, output_tokens: 0,
                total_tokens: 0, retry_count: 0, anomalies: [], errors: [],
              },
            },
          },
        }}
      />,
    );

    expect(screen.getByText("信息来源与运行验收")).toBeInTheDocument();
    expect(screen.getByText("1/3 通过 · 2 项未满足")).toBeInTheDocument();
    expect(screen.getByText("实际：命中 0/1 次")).toBeInTheDocument();
    expect(screen.getAllByText("验收未通过")).toHaveLength(2);
    expect(screen.getByText("工具调用与回答验收")).toBeInTheDocument();
    expect(screen.getByText("本次评分扣 1 分 · 专业准确性与边界")).toBeInTheDocument();
  });
});
