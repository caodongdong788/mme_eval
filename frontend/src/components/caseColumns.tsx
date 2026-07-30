import { type ReactNode } from "react";
import { Tooltip, Typography } from "antd";
import { Link } from "react-router-dom";
import { CaseRow } from "../api/index";

const RAG_STATUS: Record<NonNullable<CaseRow["rag_status"]>, { label: string; kind: string }> = {
  hit: { label: "已触发并命中", kind: "pass" },
  miss: { label: "已触发未命中", kind: "warn" },
  failed: { label: "调用失败", kind: "fail" },
  triggered: { label: "已触发", kind: "warn" },
  not_triggered: { label: "未触发", kind: "muted" },
  unknown: { label: "链路未同步", kind: "muted" },
};

// 状态圆点 + 文字（去面状彩色 Tag；样式见 styles.css .status-dot）。
function Dot({ kind, children }: { kind: string; children: ReactNode }) {
  return <span className={`status-dot status-dot--${kind}`}>{children}</span>;
}

// 用例明细表列定义工厂；依赖 runId（详情跳转）与 tagLabel（失败标签中文化）。
export function buildCaseColumns(runId: number, tagLabel: (k: string) => string) {
  return [
    {
      title: "场景描述",
      dataIndex: "sub_scenario",
      render: (s: string, r: CaseRow) => (
        <Link
          to={`/runs/${runId}/cases/${r.sample_id}`}
          state={{ from: { to: `/runs/${runId}`, state: { tab: "detail" }, label: "用例列表" } }}
          className="dash-table__link"
        >
          {s || r.sample_id}
        </Link>
      ),
    },
    { title: "类别", dataIndex: "scenario" },
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
        return <Dot kind={item.kind}>{item.label}</Dot>;
      },
    },
    {
      title: "总分",
      dataIndex: "composite_score",
      render: (v?: number) => (v == null ? "-" : `${v.toFixed(1)}/45`),
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
      title: "综合评级",
      dataIndex: "grade",
      render: (grade: string, row: CaseRow) => {
        const label = grade || (row.release_passed ? "合格" : "不合格");
        const kind = label.includes("不合格") ? "fail" : label === "合格" ? "warn" : "pass";
        return <Dot kind={kind}>{label}</Dot>;
      },
    },
    {
      title: "稳定性",
      dataIndex: "stability",
      render: (s: string) =>
        s === "stable_pass" ? (
          <Dot kind="pass">稳过</Dot>
        ) : s === "flaky" ? (
          <Dot kind="warn">抖动</Dot>
        ) : (
          <Dot kind="fail">稳挂</Dot>
        ),
    },
    {
      title: "失败标签",
      dataIndex: "failure_tags",
      render: (tags: string[]) =>
        (tags || []).length ? (
          <Dot kind="fail">{(tags || []).map(tagLabel).join("、")}</Dot>
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
              <Dot kind={r.verdict === "agree" ? "pass" : "warn"}>
                {r.verdict === "agree" ? "同意" : "推翻"}
              </Dot>
            </span>
          </Tooltip>
        );
      },
    },
  ];
}
