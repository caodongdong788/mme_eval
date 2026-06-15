import { Button, Card, Select, Table, Tag, Typography } from "antd";
import { FilterOutlined } from "@ant-design/icons";
import type { PairwiseCaseVerdict, PairwiseDetail } from "../api/index";
import { DIM_LABEL } from "../labels";
import type { usePairwiseDetail } from "../hooks/usePairwiseDetail";
import { PairwiseExpandedRow } from "./PairwiseExpandedRow";
import {
  PAIRWISE_CONFIDENCE_HINT,
  PAIRWISE_DIMENSION_HINT,
  PairwiseConfidenceTag,
  PairwiseHeaderHint,
  PairwiseVerdictTag,
} from "./PairwiseVerdictTags";

const { Text } = Typography;

type PairwiseDetailState = ReturnType<typeof usePairwiseDetail>;

function PairwiseReasonCell({ r }: { r: PairwiseCaseVerdict }) {
  const sensitive =
    !r.human_calibrated && r.confidence_kind === "order" && r.winner === "tie";
  const runs = r.order_runs || [];
  if (sensitive && runs.length === 2) {
    const phrase = (w: string) => (w === "A" ? "判 A 更优" : w === "B" ? "判 B 更优" : "判持平");
    return (
      <div style={{ fontSize: 13 }}>
        <div>
          <Tag color="default">顺序① 上=A</Tag>
          {phrase(runs[0].winner)}：{runs[0].reason || "—"}
        </div>
        <div style={{ marginTop: 4 }}>
          <Tag color="green">顺序② 上=B</Tag>
          {phrase(runs[1].winner)}：{runs[1].reason || "—"}
        </div>
        <Text type="secondary" style={{ fontSize: 11 }}>
          两次判定不一致（顺序敏感）→ 判持平，建议人工复核
        </Text>
      </div>
    );
  }
  return <>{r.reason}</>;
}

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
  expandedKeys,
  setExpandedKeys,
  setCalibrateVerdict,
  runAName,
  runBName,
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
  | "expandedKeys"
  | "setExpandedKeys"
  | "setCalibrateVerdict"
  | "runAName"
  | "runBName"
>) {
  return (
    <Card title="逐用例对比">
      <div className="case-toolbar">
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
          {hasActiveFilters && (
            <Button
              type="link"
              size="small"
              onClick={resetFilters}
              style={{ paddingInline: 0 }}
            >
              重置
            </Button>
          )}
        </div>
      </div>
      <Table<PairwiseCaseVerdict>
        rowKey="sample_id"
        dataSource={filtered}
        size="small"
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
              Object.entries(r.dimension_winners || {})
                .filter(([, w]) => w !== "tie")
                .map(([dim, w]) => (
                  <Tag key={dim} color={w === "B" ? "green" : "default"}>
                    {DIM_LABEL[dim] || dim}={w}
                  </Tag>
                )),
          },
          {
            title: "操作",
            width: 72,
            render: (_, r) => (
              <Button type="link" size="small" onClick={() => setCalibrateVerdict(r)}>
                校准
              </Button>
            ),
          },
          {
            title: "理由",
            render: (_, r) => <PairwiseReasonCell r={r} />,
          },
        ]}
        expandable={{
          expandedRowKeys: expandedKeys,
          onExpandedRowsChange: (keys) => setExpandedKeys(keys as string[]),
          expandedRowRender: (r) => (
            <PairwiseExpandedRow
              runAId={detail.run_a_id}
              runBId={detail.run_b_id}
              sampleId={r.sample_id}
              runAName={runAName}
              runBName={runBName}
              comparisonId={comparisonId}
            />
          ),
        }}
      />
    </Card>
  );
}
