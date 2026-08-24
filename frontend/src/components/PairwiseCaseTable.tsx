import { useState } from "react";
import { Button, Select, Space, Table, Tag, Typography } from "antd";
import { EyeOutlined, FilterOutlined } from "@ant-design/icons";
import type { PairwiseCaseVerdict, PairwiseDetail } from "../api/index";
import type { usePairwiseDetail } from "../hooks/usePairwiseDetail";
import { normalizeScoringStandard, pairwiseDimensionLabel } from "../utils/scoringStandards";
import { DashTableLink } from "./DashTableActions";
import { DashPanel } from "./DashPanel";
import { PairwiseCaseDetailDrawer } from "./PairwiseCaseDetailDrawer";
import {
  PAIRWISE_CONFIDENCE_HINT,
  PAIRWISE_DIMENSION_HINT,
  PairwiseConfidenceTag,
  PairwiseHeaderHint,
  PairwiseVerdictTag,
} from "./PairwiseVerdictTags";

const { Text } = Typography;

const RAG_STATUS_LABEL: Record<string, { label: string; color: string }> = {
  hit: { label: "命中", color: "green" },
  miss: { label: "已调未命中", color: "orange" },
  failed: { label: "调用失败", color: "red" },
  triggered: { label: "已调用", color: "blue" },
  not_triggered: { label: "未触发", color: "default" },
  unknown: { label: "未知", color: "default" },
};

function ragStatusTag(side: "A" | "B", status: string) {
  const item = RAG_STATUS_LABEL[status] || RAG_STATUS_LABEL.unknown;
  return <Tag color={item.color}>{side} · {item.label}</Tag>;
}

type PairwiseDetailState = ReturnType<typeof usePairwiseDetail>;

export function PairwiseCaseTable({
  comparisonId,
  detail,
  filtered,
  conclusionFilter,
  setConclusionFilter,
  ragFilter,
  setRagFilter,
  confidenceFilter,
  setConfidenceFilter,
  hasActiveFilters,
  resetFilters,
  tablePage,
  setTablePage,
  runAName,
  runBName,
  onSaved,
}: {
  comparisonId: number;
  detail: PairwiseDetail;
} & Pick<
  PairwiseDetailState,
  | "filtered"
  | "conclusionFilter"
  | "setConclusionFilter"
  | "ragFilter"
  | "setRagFilter"
  | "confidenceFilter"
  | "setConfidenceFilter"
  | "hasActiveFilters"
  | "resetFilters"
  | "tablePage"
  | "setTablePage"
  | "runAName"
  | "runBName"
> & { onSaved: () => void }) {
  const [detailVerdict, setDetailVerdict] = useState<PairwiseCaseVerdict | null>(null);
  const isModelComparison = normalizeScoringStandard(detail.scoring_standard) === "model_comparison";

  return (
    <DashPanel title="逐用例对比" bodyClassName="dash-panel__body--flush">
      <div className="case-toolbar dash-filter-bar">
        <span className="case-toolbar__lead">
          <FilterOutlined />
          筛选
        </span>
        <Select
          allowClear
          placeholder="结论"
          value={conclusionFilter}
          onChange={setConclusionFilter}
          options={[
            { value: "A", label: "A 更好" },
            { value: "B", label: "B 更好" },
            { value: "tie", label: "持平" },
          ]}
        />
        <Select
          allowClear
          placeholder="真实 RAG"
          value={ragFilter}
          onChange={setRagFilter}
          options={[
            { value: "triggered", label: "已触发" },
            { value: "not_triggered", label: "未触发" },
            { value: "unknown", label: "状态未知" },
          ]}
        />
        <Select
          allowClear
          placeholder="置信"
          value={confidenceFilter}
          onChange={setConfidenceFilter}
          options={[
            { value: "high", label: "高" },
            { value: "order", label: "低 · 顺序敏感" },
            ...(!isModelComparison ? [{ value: "safety", label: "低 · 安全存疑" }] : []),
            { value: "human", label: "人工校准" },
          ]}
        />
        <div className="case-toolbar__right">
          {hasActiveFilters && <DashTableLink onClick={resetFilters}>重置</DashTableLink>}
        </div>
      </div>
      <Table<PairwiseCaseVerdict>
        className="dash-table pairwise-case-table"
        rowKey="sample_id"
        dataSource={filtered}
        size="small"
        tableLayout="auto"
        pagination={{
          pageSize: 20,
          current: tablePage,
          onChange: (p) => setTablePage(p),
        }}
        rowClassName={(r) => (r.winner === "A" ? "pairwise-regress-row" : "")}
        columns={[
          {
            title: "用例",
            render: (_, r) => {
              const desc = r.sub_scenario || r.scenario || r.sample_id;
              return (
                <div style={{ maxWidth: 360 }}>
                  <div style={{ fontSize: 13 }}>{desc}</div>
                  {desc !== r.sample_id && (
                    <Text type="secondary" className="mono" style={{ fontSize: 11 }}>
                      {r.sample_id}
                    </Text>
                  )}
                </div>
              );
            },
          },
          { title: "结论", render: (_, r) => <PairwiseVerdictTag verdict={r} /> },
          {
            title: "真实 RAG",
            render: (_, r) => (
              <Space size={[2, 4]} wrap>
                {ragStatusTag("A", r.rag_status_a)}
                {ragStatusTag("B", r.rag_status_b)}
              </Space>
            ),
          },
          {
            title: <PairwiseHeaderHint label="置信" hint={PAIRWISE_CONFIDENCE_HINT} />,
            dataIndex: "confidence",
            render: (_: string, r) => <PairwiseConfidenceTag verdict={r} />,
          },
          {
            title: <PairwiseHeaderHint label="维度" hint={PAIRWISE_DIMENSION_HINT} />,
            render: (_, r) =>
              Object.entries(r.dimension_winners || {}).filter(([, w]) => w !== "tie").length ? (
                <Space size={[2, 4]} wrap>
                  {Object.entries(r.dimension_winners || {})
                    .filter(([, w]) => w !== "tie")
                    .map(([dim, w]) => (
                      <Tag key={dim} color={w === "B" ? "green" : "default"}>
                        {pairwiseDimensionLabel(dim)}={w === "A" ? "A 更好" : w === "B" ? "B 更好" : "不适用"}
                      </Tag>
                    ))}
                </Space>
              ) : (
                <Text type="secondary">—</Text>
              ),
          },
          {
            title: "操作",
            width: 112,
            render: (_, r) => (
              <Button type="link" size="small" icon={<EyeOutlined />} onClick={() => setDetailVerdict(r)}>
                查看明细
              </Button>
            ),
          },
        ]}
      />
      <PairwiseCaseDetailDrawer
        open={detailVerdict != null}
        verdict={detailVerdict}
        comparisonId={comparisonId}
        runAId={detail.run_a_id}
        runBId={detail.run_b_id}
        runAName={runAName}
        runBName={runBName}
        scoringStandard={detail.scoring_standard}
        onClose={() => setDetailVerdict(null)}
        onSaved={onSaved}
      />
    </DashPanel>
  );
}
