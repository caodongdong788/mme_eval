import { type ReactNode } from "react";
import { Space, Tag, Tooltip, Typography } from "antd";
import { Link } from "react-router-dom";
import { CaseRow } from "../api/index";
import { failureTagHint } from "../hooks/useConfigLabelMap";
import { getCaseFinalVerdict, getCaseRuntimeAcceptance } from "../utils/caseFilters";

const RAG_STATUS: Record<NonNullable<CaseRow["rag_status"]>, { label: string; kind: string }> = {
  hit: { label: "已触发并命中", kind: "pass" },
  miss: { label: "已触发未命中", kind: "warn" },
  failed: { label: "调用失败", kind: "fail" },
  triggered: { label: "已触发", kind: "warn" },
  not_triggered: { label: "未触发", kind: "muted" },
  unknown: { label: "快照未获取", kind: "muted" },
};

// 状态圆点 + 文字（去面状彩色 Tag；样式见 styles.css .status-dot）。
function dot(kind: string, children: ReactNode) {
  return <span className={`status-dot status-dot--${kind}`}>{children}</span>;
}

// 用例明细表列定义工厂；依赖 runId（详情跳转）与 tagLabel（失败标签中文化）。
export function buildCaseColumns(
  runId: number,
  tagLabel: (k: string) => string,
  _scoringStandard?: string,
) {
  const totalMax = 40;
  const executionFailed = (row: CaseRow) => getCaseFinalVerdict(row) === "执行失败";
  return [
    {
      title: "场景描述",
      dataIndex: "sub_scenario",
      render: (s: string, r: CaseRow) => (
        <Link
          to={`/runs/${runId}/cases/${r.sample_id}`}
          state={{ from: { to: `/runs/${runId}?tab=detail`, label: "用例列表" } }}
          className="dash-table__link"
        >
          {s || r.sample_id}
        </Link>
      ),
    },
    {
      title: "类别",
      dataIndex: "case_type",
      render: (value: string) => value || <Typography.Text type="secondary">-</Typography.Text>,
    },
    { title: "Level", dataIndex: "level" },
    {
      title: "轮数",
      dataIndex: "n_turns",
      render: (n?: number) => {
        const turns = n ?? 1;
        return turns > 1 ? (
          <span className="mono">{turns} 轮</span>
        ) : (
          <Typography.Text type="secondary">单轮</Typography.Text>
        );
      },
    },
    {
      title: "医学文献 RAG",
      dataIndex: "rag_status",
      render: (value?: CaseRow["rag_status"]) => {
        const item = RAG_STATUS[value || "unknown"];
        return dot(item.kind, item.label);
      },
    },
    {
      title: "总分",
      dataIndex: "composite_score",
      render: (v: number | undefined, row: CaseRow) =>
        executionFailed(row)
          ? dot("fail", "未产生回答")
          : row.judge_error ? dot("warn", "判分异常") : (v == null ? "-" : `${v.toFixed(1)}/${totalMax}`),
    },
    {
      title: "指南得分",
      dataIndex: "guideline_earned",
      render: (_: number | null | undefined, r: CaseRow) => {
        if (r.guideline_max) return `${r.guideline_earned ?? 0}/${r.guideline_max}`;
        return <Typography.Text type="secondary">无指南项</Typography.Text>;
      },
    },
    {
      title: "质量评级",
      dataIndex: "grade",
      render: (grade: string, row: CaseRow) => {
        if (executionFailed(row)) return dot("fail", "执行失败");
        if (row.judge_error) return dot("warn", "判分异常");
        const label = grade || (row.release_passed ? "合格" : "不合格");
        const kind = label.includes("不合格") ? "fail" : label === "合格" ? "warn" : "pass";
        return dot(kind, label);
      },
    },
    {
      key: "runtime_acceptance",
      title: "运行验收",
      dataIndex: "release_passed",
      render: (_passed: boolean, row: CaseRow) => {
        const acceptance = getCaseRuntimeAcceptance(row);
        return dot(
          acceptance === "合格" ? "pass" : acceptance === "不合格" ? "fail" : "warn",
          acceptance
        );
      },
    },
    {
      key: "final_verdict",
      title: "最终结论",
      dataIndex: "release_passed",
      render: (_passed: boolean, row: CaseRow) => {
        const verdict = getCaseFinalVerdict(row);
        return dot(
          verdict === "通过" ? "pass" : verdict === "不通过" ? "fail" : "warn",
          verdict
        );
      },
    },
    {
      title: "稳定性",
      dataIndex: "stability",
      render: (s: string) =>
        s === "stable_pass" ? (
          dot("pass", "稳定通过")
        ) : s === "flaky" ? (
          dot("warn", "结果波动")
        ) : (
          dot("fail", "稳定失败")
        ),
    },
    {
      title: "主要问题",
      dataIndex: "failure_tags",
      render: (tags: string[]) =>
        (tags || []).length ? (
          <Space size={[4, 4]} wrap>
            {(tags || []).map((tag) => (
              <Tooltip title={failureTagHint(tag)} key={tag}>
                <Tag color={tag === "medical_safety_risk" ? "red" : "volcano"}>
                  {tagLabel(tag)}
                </Tag>
              </Tooltip>
            ))}
          </Space>
        ) : (
          <Typography.Text type="secondary">-</Typography.Text>
        ),
    },
    {
      title: "人审结果",
      dataIndex: "review",
      render: (r: CaseRow["review"]) => {
        if (!r) return <Typography.Text type="secondary">-</Typography.Text>;
        const tip = (
          <div>
            {r.reviewer && <div>审核人：{r.reviewer}</div>}
            <div>建议：{r.suggestion || "（无）"}</div>
            <div>备注：{r.comment || "（无）"}</div>
            {r.count > 1 && <div>共 {r.count} 条裁定（显示最新）</div>}
          </div>
        );
        return (
          <Tooltip title={tip}>
            <span style={{ cursor: "help" }}>
              {dot(
                r.verdict === "agree" ? "pass" : "warn",
                r.verdict === "agree" ? "同意" : "推翻"
              )}
            </span>
          </Tooltip>
        );
      },
    },
  ];
}
