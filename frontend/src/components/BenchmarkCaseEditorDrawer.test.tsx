import { fireEvent, screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { renderWithProviders } from "../test/renderWithProviders";
import { BenchmarkCaseEditorDrawer } from "./BenchmarkCaseEditorDrawer";

const testCase = {
  schema_version: "2.0",
  sample_id: "case_55",
  scenario: "报告解读",
  case_type: "检查报告与指标解读",
  is_bug: "产品优化",
  level: "L2",
  initial_state: { user_profile: { 年龄: "36岁" }, Timeline: [] },
  turns: [{ role: "user", content: "帮我解读报告" }],
  evaluation: {
    dimension_criteria: {
      medical_safety: {
        criteria: ["不得遗漏危险信号"],
        reference_answers: ["先说明危险信号，再建议尽快就医。"],
      },
    },
    guidelines: [],
  },
};

describe("BenchmarkCaseEditorDrawer criteria variant", () => {
  it("uses the benchmark structured editor without exposing YAML", () => {
    const onChange = vi.fn();
    renderWithProviders(
      <BenchmarkCaseEditorDrawer
        open
        loading={false}
        saving={false}
        source="uploaded"
        caseFile="cases.yaml"
        value={testCase}
        onChange={onChange}
        onClose={vi.fn()}
        variant="criteria"
        title="改判据 · 报告解读"
        benchmarkLabel="#12「真实患者数据集benchmark」"
        onOverwrite={vi.fn()}
      />
    );

    expect(screen.getByText("基本信息")).toBeInTheDocument();
    expect(screen.getByText("账号初始化数据")).toBeInTheDocument();
    expect(screen.getByText("八维评测要求")).toBeInTheDocument();
    expect(screen.getByText("指南扣分点（0）")).toBeInTheDocument();
    expect(screen.getByText("运行断言（0）")).toBeInTheDocument();
    expect(screen.queryByText("查看源 YAML")).not.toBeInTheDocument();
    expect(screen.queryByText("源 YAML（只读）")).not.toBeInTheDocument();

    fireEvent.change(screen.getByDisplayValue("报告解读"), {
      target: { value: "报告复核" },
    });
    expect(onChange).toHaveBeenCalledWith(expect.objectContaining({ scenario: "报告复核" }));

    fireEvent.click(screen.getByText("八维评测要求"));
    fireEvent.click(screen.getByText("医学安全性"));
    expect(screen.getByText("好答案（可选）")).toBeInTheDocument();
    expect(screen.getByDisplayValue("先说明危险信号，再建议尽快就医。")).toBeInTheDocument();
  });

  it("shows optional account modules and every assertion field in the visual editor", () => {
    const expandedCase = {
      ...testCase,
      initial_state: {
        ...testCase.initial_state,
        profile_memory: ["[沟通] 先给结论，再列数据"],
        response_preferences: [{ preference: "简洁回答", basis: "用户明确提出" }],
        medical_documents: [{
          ref: "lab_1",
          title: "血常规",
          document_date: "2026-08-20",
          document_type: "lab",
          metrics: [{ name: "白细胞", value: 3.2, unit: "10^9/L", measured_at: "2026-08-20", is_trend_metric: true }],
        }],
        chat_history: [{ ref: "history_1", title: "既往咨询", started_at: "2026-07-04T10:00:00+08:00", messages: [{ role: "user", content: "上次指标是多少", created_at: "2026-07-04T10:00:10+08:00" }] }],
        tool_state: {
          scheduled_tasks: [{ ref: "schedule_1", task_name: "复诊提醒", due_at: "2026-09-01T09:00:00+08:00", message: "请复诊", purpose: "review_reminder", time_source: "user_explicit", schedule_type: "once", timezone: "Asia/Shanghai", route: "/medical-records" }],
          check_ins: [{ ref: "temperature_1", category_key: "temperature", category_name: "体温", title: "今日体温", recorded_at: "2026-08-20T08:00:00+08:00", values: { temperature: 36.6, fever: false }, fields: [{ key: "temperature", label: "体温", type: "number", unit: "℃", required: true }, { key: "fever", label: "是否发热", type: "boolean", required: true }], tags: ["复查观察"] }],
          undercurrent_tasks: [{ ref: "monitor_wbc", kind: "monitor", status: "active", next_due_at: "2026-09-01T09:00:00+08:00", priority: 10, payload: { metric_names: ["白细胞"], reason: "关注指标变化" } }],
        },
      },
      evaluation: {
        ...testCase.evaluation,
        assertions: [{ id: "a01", type: "tool_call", description: "必须读取病例指标", blocking: true, on_unavailable: "fail", name: "read_medical_metrics", min_count: 1 }],
      },
    };
    renderWithProviders(
      <BenchmarkCaseEditorDrawer open loading={false} saving={false} source="uploaded" caseFile="cases.yaml" value={expandedCase} onChange={vi.fn()} onClose={vi.fn()} />
    );

    const contextTabs = screen.getAllByText("账号初始化数据");
    fireEvent.click(contextTabs[contextTabs.length - 1]);
    expect(screen.getByRole("tab", { name: /用户档案/ })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: /过往事实/ })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: /长期画像/ })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: /回复偏好/ })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: /病例夹/ })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: /历史对话/ })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: /工具业务数据/ })).toBeInTheDocument();

    fireEvent.click(screen.getByRole("tab", { name: /长期画像/ }));
    expect(screen.getByText("长期画像记忆（USER.md）")).toBeInTheDocument();
    expect(screen.getByRole("combobox", { name: "画像分类 1" })).toBeInTheDocument();
    expect(screen.getByText("沟通")).toBeInTheDocument();
    expect(screen.getByRole("textbox", { name: "画像内容 1" })).toHaveValue("先给结论，再列数据");

    fireEvent.click(screen.getByRole("tab", { name: /回复偏好/ }));
    expect(screen.getByRole("textbox", { name: "偏好内容 1" })).toHaveValue("简洁回答");
    expect(screen.getByRole("textbox", { name: "偏好依据 1" })).toHaveValue("用户明确提出");
    expect(screen.getByText("偏好内容")).toBeInTheDocument();
    expect(screen.getByText("偏好依据（可选）")).toBeInTheDocument();
    expect(screen.queryByDisplayValue("preference")).not.toBeInTheDocument();
    expect(screen.queryByDisplayValue("basis")).not.toBeInTheDocument();
    expect(screen.queryByText("新增字段")).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("tab", { name: /病例夹/ }));
    expect(screen.getByText("病例夹与结构化指标")).toBeInTheDocument();
    expect(screen.getByText("报告基础信息")).toBeInTheDocument();
    expect(screen.getByText("文档标识（唯一）")).toBeInTheDocument();
    expect(screen.getByDisplayValue("lab_1")).toBeInTheDocument();
    expect(screen.queryByText("报告原始字段")).not.toBeInTheDocument();
    expect(screen.getByText("结构化指标")).toBeInTheDocument();
    expect(screen.getByText("用于前后对比")).toBeInTheDocument();
    expect(screen.queryByText("纳入趋势指标")).not.toBeInTheDocument();
    expect(screen.queryByText("扩展属性（可选）")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: /新增报告\/病历/ })).toBeInTheDocument();
    expect(screen.getByDisplayValue("白细胞")).toBeInTheDocument();
    expect(screen.getByDisplayValue("3.2")).toBeInTheDocument();
    expect(screen.queryByText(/\{"name":"白细胞"/)).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("tab", { name: /历史对话/ }));
    expect(screen.getAllByText("历史对话").length).toBeGreaterThan(1);
    expect(screen.getByText("会话标识（唯一）")).toBeInTheDocument();
    expect(screen.getByText("会话标题")).toBeInTheDocument();
    expect(screen.getByText("会话开始时间（可选）")).toBeInTheDocument();
    expect(screen.getByText("对话消息")).toBeInTheDocument();
    expect(screen.queryByText("说话方")).not.toBeInTheDocument();
    expect(screen.getByText("消息内容")).toBeInTheDocument();
    expect(screen.getByText("消息时间（可选）")).toBeInTheDocument();
    expect(screen.getByDisplayValue("上次指标是多少")).toBeInTheDocument();
    expect(screen.queryByDisplayValue("ref")).not.toBeInTheDocument();
    expect(screen.queryByDisplayValue("messages")).not.toBeInTheDocument();
    expect(screen.queryByDisplayValue("started_at")).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("tab", { name: /工具业务数据/ }));
    expect(screen.getAllByText("工具业务数据").length).toBeGreaterThan(1);
    expect(screen.getByRole("tab", { name: /提醒任务/ })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: /打卡记录/ })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: /暗流任务/ })).toBeInTheDocument();
    expect(screen.getByText("任务标识（唯一）")).toBeInTheDocument();
    expect(screen.getByText("提醒名称")).toBeInTheDocument();
    expect(screen.getByText("执行时间")).toBeInTheDocument();
    expect(screen.getByText("提醒用途")).toBeInTheDocument();
    expect(screen.getByText("复查提醒")).toBeInTheDocument();
    expect(screen.queryByDisplayValue("task_name")).not.toBeInTheDocument();
    expect(screen.queryByDisplayValue("due_at")).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("tab", { name: /打卡记录/ }));
    expect(screen.getByText("记录标识（唯一）")).toBeInTheDocument();
    expect(screen.getByText("打卡类型名称")).toBeInTheDocument();
    expect(screen.getByText("打卡数据")).toBeInTheDocument();
    expect(screen.getByText("字段展示配置（可选）")).toBeInTheDocument();
    expect(screen.getAllByText("数据项").length).toBeGreaterThan(0);
    expect(screen.getByText("体温数值")).toBeInTheDocument();
    expect(screen.getByText("是否发热数值")).toBeInTheDocument();
    expect(screen.queryByText("数据项标识")).not.toBeInTheDocument();
    expect(screen.getAllByText("数据类型").length).toBeGreaterThan(0);
    expect(screen.queryByDisplayValue("values")).not.toBeInTheDocument();
    expect(screen.queryByDisplayValue("fields")).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("tab", { name: /暗流任务/ }));
    expect(screen.getByText("任务类型")).toBeInTheDocument();
    expect(screen.getByText("任务状态")).toBeInTheDocument();
    expect(screen.getAllByText("指标监测").length).toBeGreaterThan(0);
    expect(screen.getByText("任务参数")).toBeInTheDocument();
    expect(screen.getAllByText("参数名称").length).toBeGreaterThan(0);
    expect(screen.getAllByText("参数内容").length).toBeGreaterThan(0);
    expect(screen.queryByDisplayValue("payload")).not.toBeInTheDocument();

    const assertionTabs = screen.getAllByText("运行断言（1）");
    fireEvent.click(assertionTabs[assertionTabs.length - 1]);
    expect(screen.getByText("工具调用检查")).toBeInTheDocument();
    expect(screen.getByText("检查名称")).toBeInTheDocument();
    expect(screen.getByDisplayValue("必须读取病例指标")).toBeInTheDocument();
    expect(screen.getByText("检查条件")).toBeInTheDocument();
    expect(screen.getAllByText("read_medical_metrics").length).toBeGreaterThan(0);
    expect(screen.getByRole("tab", { name: /工具调用/ })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: /数据命中/ })).toBeInTheDocument();
    expect(screen.queryByRole("tab", { name: /状态结果/ })).not.toBeInTheDocument();
    expect(screen.getByRole("tab", { name: /回答要求/ })).toBeInTheDocument();
    expect(screen.queryByText("规则编号")).not.toBeInTheDocument();
    expect(screen.getByText("目标工具")).toBeInTheDocument();
    expect(screen.getByText("读取病例指标")).toBeInTheDocument();
    expect(screen.getByText(/读取病例夹中的结构化检查指标/)).toBeInTheDocument();
    expect(screen.queryByText("不可观测时")).not.toBeInTheDocument();
    expect(screen.queryByText("阻断性断言")).not.toBeInTheDocument();
    expect(screen.queryByText("性能预算")).not.toBeInTheDocument();
  });

  it("explains every data source separately from tool invocation", () => {
    const value = {
      ...testCase,
      evaluation: {
        ...testCase.evaluation,
        assertions: [{
          id: "rag_hit",
          type: "retrieval",
          description: "医学文献检索必须返回可用证据",
          name: "medical_literature",
          min_count: 1,
        }],
      },
    };
    renderWithProviders(
      <BenchmarkCaseEditorDrawer open loading={false} saving={false} source="uploaded" caseFile="cases.yaml" value={value} onChange={vi.fn()} onClose={vi.fn()} />
    );

    const assertionTabs = screen.getAllByText("运行断言（1）");
    fireEvent.click(assertionTabs[assertionTabs.length - 1]);
    const retrievalTabs = screen.getAllByRole("tab", { name: /数据命中/ });
    fireEvent.click(retrievalTabs[retrievalTabs.length - 1]);

    expect(screen.getByText("目标数据来源")).toBeInTheDocument();
    expect(screen.getByText("最少命中次数")).toBeInTheDocument();
    expect(screen.getAllByText("literature_rag").length).toBeGreaterThan(0);
    expect(screen.getByText("医学文献 RAG")).toBeInTheDocument();
    expect(screen.getByText(/最终采用了可用于回答的论文、指南、药品说明书或专家 QA 证据/)).toBeInTheDocument();
    expect(screen.queryByText(/历史名称 medical_literature/)).not.toBeInTheDocument();
    expect(screen.queryByText("目标检索来源")).not.toBeInTheDocument();
  });

  it("groups guidelines by dimension in doctor, nurse, patient order", () => {
    const groupedCase = {
      ...testCase,
      evaluation: {
        ...testCase.evaluation,
        guidelines: [
          { id: "g01", dimension: "empathy", criteria: ["患者检查点一"] },
          { id: "g02", dimension: "medical_safety", criteria: ["医生检查点"] },
          { id: "g03", dimension: "personalization", criteria: ["护士检查点"] },
          { id: "g04", dimension: "empathy", criteria: ["患者检查点二"] },
        ],
      },
    };
    renderWithProviders(
      <BenchmarkCaseEditorDrawer open loading={false} saving={false} source="uploaded" caseFile="cases.yaml" value={groupedCase} onChange={vi.fn()} onClose={vi.fn()} />
    );

    fireEvent.click(screen.getByText("指南扣分点（4）"));

    const roleGroups = Array.from(document.body.querySelectorAll(".case-editor-guideline-role-group"));
    expect(roleGroups).toHaveLength(3);
    expect(roleGroups[0]).toHaveTextContent("医生端");
    expect(roleGroups[0]).toHaveTextContent("医学安全性");
    expect(roleGroups[1]).toHaveTextContent("护士端");
    expect(roleGroups[1]).toHaveTextContent("个性化相关性");
    expect(roleGroups[2]).toHaveTextContent("患者端");
    expect(roleGroups[2]).toHaveTextContent("患者检查点一");
    expect(roleGroups[2]).toHaveTextContent("患者检查点二");
    expect(roleGroups[2].querySelectorAll(".case-editor-guideline-dimension-group")).toHaveLength(1);
  });

  it("adds an independent guideline item for the selected dimension", () => {
    const onChange = vi.fn();
    const groupedCase = {
      ...testCase,
      evaluation: {
        ...testCase.evaluation,
        guidelines: [
          { id: "g01", dimension: "medical_safety", criteria: ["已有检查点"], reference_answers: ["已有好答案"] },
        ],
      },
    };
    renderWithProviders(
      <BenchmarkCaseEditorDrawer open loading={false} saving={false} source="uploaded" caseFile="cases.yaml" value={groupedCase} onChange={onChange} onClose={vi.fn()} />
    );

    fireEvent.click(screen.getByText("指南扣分点（1）"));
    const dimensionGroups = document.body.querySelectorAll<HTMLElement>(".case-editor-guideline-dimension-group");
    fireEvent.click(within(dimensionGroups[dimensionGroups.length - 1]!).getByRole("button", { name: /新增扣分项/ }));

    expect(onChange).toHaveBeenLastCalledWith(expect.objectContaining({
      evaluation: expect.objectContaining({
        guidelines: [
          groupedCase.evaluation.guidelines[0],
          expect.objectContaining({
            id: "g02",
            dimension: "medical_safety",
            criteria: [""],
            reference_answers: [""],
          }),
        ],
      }),
    }));
  });

  it("automatically assigns a rule number when adding an assertion", () => {
    const onChange = vi.fn();
    const value = {
      ...testCase,
      evaluation: {
        ...testCase.evaluation,
        assertions: [{ id: "a01", type: "tool_call", description: "读取指标", name: "read_medical_metrics", min_count: 1 }],
      },
    };
    renderWithProviders(
      <BenchmarkCaseEditorDrawer open loading={false} saving={false} source="uploaded" caseFile="cases.yaml" value={value} onChange={onChange} onClose={vi.fn()} />
    );

    const assertionTabs = screen.getAllByText("运行断言（1）");
    fireEvent.click(assertionTabs[assertionTabs.length - 1]);
    const transcriptTabs = screen.getAllByRole("tab", { name: /回答要求/ });
    fireEvent.click(transcriptTabs[transcriptTabs.length - 1]);
    const addButtons = screen.getAllByRole("button", { name: /新增回答要求检查/ });
    fireEvent.click(addButtons[addButtons.length - 1]);

    expect(onChange).toHaveBeenLastCalledWith(expect.objectContaining({
      evaluation: expect.objectContaining({
        assertions: [
          value.evaluation.assertions[0],
          expect.objectContaining({ id: "a02", type: "transcript", contains: "", scope: "assistant_final", dimensions: [], deduction: 0 }),
        ],
      }),
    }));
  });

});
