import { useState } from "react";
import { Button, Select, Space, Table, Tag, Typography } from "antd";
import { EyeOutlined, FilterOutlined } from "@ant-design/icons";
import type { PairwiseCaseVerdict, PairwiseDetail } from "../api/index";
import { DIM_LABEL } from "../labels";
import type { usePairwiseDetail } from "../hooks/usePairwiseDetail";
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

type PairwiseDetailState = ReturnType<typeof usePairwiseDetail>;

export function PairwiseCaseTable({
  comparisonId,
  detail,
  filtered,
  conclusionFilter,
  setConclusionFilter,
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
          placeholder="置信"
          value={confidenceFilter}
          onChange={setConfidenceFilter}
          options={[
            { value: "high", label: "高" },
            { value: "order", label: "低 · 顺序敏感" },
            { value: "safety", label: "低 · 安全存疑" },
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
                        {DIM_LABEL[dim] || dim}={w}
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
        onClose={() => setDetailVerdict(null)}
        onSaved={onSaved}
      />
    </DashPanel>
  );
}
