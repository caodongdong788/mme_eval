import { type ReactNode } from "react";
import { Tooltip, Typography } from "antd";
import { Link } from "react-router-dom";
import { CaseRow } from "../api";

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
      title: "综合分",
      dataIndex: "composite_score",
      render: (v?: number) => (v == null ? "-" : v.toFixed(2)),
    },
    {
      title: "指南匹配率",
      dataIndex: "guideline_match_rate",
      render: (v: number | null | undefined, r: CaseRow) => {
        if (r.guideline_total && r.guideline_total > 0) {
          const pct = Math.round(((r.guideline_matched ?? 0) / r.guideline_total) * 100);
          return `${pct}%（${r.guideline_matched ?? 0}/${r.guideline_total}）`;
        }
        if (v == null) return <Typography.Text type="secondary">无锚点</Typography.Text>;
        return `${Math.round(v * 100)}%`;
      },
    },
    {
      title: "上线判定",
      dataIndex: "release_passed",
      render: (v: boolean) =>
        v ? <Dot kind="pass">通过</Dot> : <Dot kind="fail">失败</Dot>,
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
    {
      title: "追踪链路",
      dataIndex: "langfuse_trace_url",
      render: (url?: string | null) =>
        url ? (
          <Tooltip title="在 Langfuse 打开该用例的完整流程追踪">
            <a href={url} target="_blank" rel="noreferrer">
              查看链路
            </a>
          </Tooltip>
        ) : (
          <Typography.Text type="secondary">-</Typography.Text>
        ),
    },
  ];
}
