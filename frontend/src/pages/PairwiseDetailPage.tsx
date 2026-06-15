import { useCallback, useEffect, useRef, useState } from "react";
import {
  Alert,
  Button,
  Card,
  Col,
  Empty,
  Result,
  Row,
  Select,
  Space,
  Spin,
  Statistic,
  Table,
  Tag,
  Tooltip,
  Typography,
} from "antd";
import {
  LoadingOutlined,
  ArrowRightOutlined,
  FilterOutlined,
  QuestionCircleOutlined,
} from "@ant-design/icons";
import { Link, useLocation, useParams } from "react-router-dom";
import PairwiseCalibrateModal from "../components/PairwiseCalibrateModal";
import {
  api,
  type PairwiseCaseVerdict,
  type PairwiseConfidenceKind,
  type PairwiseDetail,
} from "../api";
import { DIM_LABEL } from "../labels";
import { formatApiError } from "../utils/apiError";

const { Text, Title } = Typography;

function verdictTag(r: PairwiseCaseVerdict) {
  const tag =
    r.winner === "A" ? (
      <Tag color="default">A 更好</Tag>
    ) : r.winner === "B" ? (
      <Tag color="green">B 更好</Tag>
    ) : (
      <Tag>持平</Tag>
    );
  if (r.human_calibrated) {
    return (
      <Space size={4}>
        {tag}
        <Tag color="purple">人工</Tag>
      </Space>
    );
  }
  return tag;
}

function confidenceTag(r: PairwiseCaseVerdict) {
  const kind = r.confidence_kind;
  if (kind === "human") {
    return (
      <Tooltip title="本条结论已由人工校准覆写，报告统计按校准值计算。">
        <Tag color="purple">人工校准</Tag>
      </Tooltip>
    );
  }
  if (kind === "high") {
    return (
      <Tooltip title="位置互换后两次判定一致（含一致判平的真平局），结论稳健。">
        <Tag color="green">高</Tag>
      </Tooltip>
    );
  }
  if (kind === "order") {
    return (
      <Tooltip title="顺序敏感：把 A/B 位置互换后两次判定不一致，结论受位置偏见影响、不稳定，建议人工复核。">
        <Tag color="orange">低 · 顺序敏感</Tag>
      </Tooltip>
    );
  }
  return (
    <Tooltip title="安全存疑：两次一致倾向某方更优，但被医疗保守规则按「安全」维度降级为持平，建议人工复核。">
      <Tag color="volcano">低 · 安全存疑</Tag>
    </Tooltip>
  );
}

const CONFIDENCE_HINT =
  "置信 = 机器判定稳健性，或人工校准。高=两次一致；低·顺序敏感/安全存疑=建议复核；人工校准=专家覆写后的有效结论。";
const DIMENSION_HINT =
  "维度 = 从三个角度看谁更好：安全（红旗分诊/处方边界/免责）、功能（是否抓住意图、信息完整、鉴别合理）、体验（清晰、共情、简洁）。仅展示分出胜负的维度。";

function HeaderHint({ label, hint }: { label: string; hint: string }) {
  return (
    <Tooltip title={hint}>
      <span style={{ cursor: "help" }}>
        {label} <QuestionCircleOutlined style={{ color: "var(--muted)" }} />
      </span>
    </Tooltip>
  );
}

function ConversationCol({
  runId,
  sampleId,
  side,
  runName,
  comparisonId,
}: {
  runId: number;
  sampleId: string;
  side: "A" | "B";
  runName: string;
  comparisonId: number;
}) {
  const [messages, setMessages] = useState<any[]>([]);
  useEffect(() => {
    api
      .getCaseDetail(runId, sampleId)
      .then((d) => setMessages(d?.trace?.messages || []))
      .catch(() => setMessages([]));
  }, [runId, sampleId]);
  return (
    <Card
      size="small"
      title={
        <span>
          <Tag color={side === "B" ? "green" : "default"} style={{ marginInlineEnd: 6 }}>
            {side}
          </Tag>
          {runName}
        </span>
      }
      extra={
        <Link
          to={`/runs/${runId}/cases/${encodeURIComponent(sampleId)}`}
          state={{
            from: {
              to: `/pairwise/${comparisonId}`,
              state: { expandedKey: sampleId },
              label: "对比明细",
            },
          }}
        >
          用例明细 <ArrowRightOutlined />
        </Link>
      }
      styles={{ body: { maxHeight: 420, overflowY: "auto" } }}
    >
      <Space direction="vertical" size={8} style={{ display: "flex" }}>
        {messages.map((m, i) => {
          const isUser = m.role === "user";
          return (
            <div key={i} style={{ alignSelf: isUser ? "flex-start" : "stretch" }}>
              <Text type="secondary" style={{ fontSize: 11 }}>
                {isUser ? "用户" : m.role === "assistant" ? "AI 回复" : m.role}
              </Text>
              <div
                style={{
                  whiteSpace: "pre-wrap",
                  background: isUser ? "var(--surface-chip)" : "transparent",
                  border: isUser ? "none" : "1px solid var(--border)",
                  borderRadius: 8,
                  padding: "6px 10px",
                  fontSize: 13,
                }}
              >
                {m.content}
              </div>
            </div>
          );
        })}
        {messages.length === 0 && <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} />}
      </Space>
    </Card>
  );
}

export default function PairwiseDetailPage() {
  const { comparisonId } = useParams();
  const location = useLocation();
  const id = Number(comparisonId);
  const [detail, setDetail] = useState<PairwiseDetail | null>(null);
  const [detailError, setDetailError] = useState<string | null>(null);
  const [conclusionFilter, setConclusionFilter] = useState<"A" | "B" | "tie" | undefined>();
  const [confidenceFilter, setConfidenceFilter] = useState<
    PairwiseConfidenceKind | undefined
  >();
  const [calibrateVerdict, setCalibrateVerdict] = useState<PairwiseCaseVerdict | null>(null);
  // 逐用例对比表的展开行与页码（受控，便于从用例明细返回时恢复现场）。
  const [expandedKeys, setExpandedKeys] = useState<string[]>([]);
  const [tablePage, setTablePage] = useState(1);
  const restoredRef = useRef(false);
  const didMountFiltersRef = useRef(false);

  const load = useCallback(() => {
    if (!id) return;
    api
      .getPairwise(id)
      .then((d) => {
        setDetail(d);
        setDetailError(null);
      })
      .catch((e) => setDetailError(formatApiError(e, "加载对比详情失败")));
  }, [id]);

  useEffect(() => {
    load();
  }, [load]);

  // 进行中时轮询。
  useEffect(() => {
    if (detail?.status === "running") {
      const t = setInterval(load, 2500);
      return () => clearInterval(t);
    }
  }, [detail?.status, load]);

  // 从用例明细「返回对比明细」时，恢复之前展开的那一行：定位到所在页并滚动入视。
  useEffect(() => {
    if (restoredRef.current || !detail) return;
    const key = (location.state as { expandedKey?: string } | null)?.expandedKey;
    if (!key) return;
    const idx = (detail.verdicts || []).findIndex((v) => v.sample_id === key);
    if (idx >= 0) {
      setExpandedKeys([key]);
      setTablePage(Math.floor(idx / 20) + 1);
      requestAnimationFrame(() => {
        document
          .querySelector(`[data-row-key="${CSS.escape(key)}"]`)
          ?.scrollIntoView({ block: "center", behavior: "smooth" });
      });
    }
    restoredRef.current = true;
  }, [detail, location.state]);

  // 筛选变化时回到第 1 页（跳过首次挂载，避免清掉上面恢复的页码）。
  useEffect(() => {
    if (!didMountFiltersRef.current) {
      didMountFiltersRef.current = true;
      return;
    }
    setTablePage(1);
  }, [conclusionFilter, confidenceFilter]);

  if (!detail)
    return detailError ? (
      <Result
        status="warning"
        title="无法加载对比详情"
        subTitle={detailError}
        extra={
          <Link to="/pairwise">
            <Button>返回 Pairwise 列表</Button>
          </Link>
        }
      />
    ) : (
      <Card loading />
    );

  const s = detail.summary || {};
  const total = s.total ?? 0;
  const aWins = s.a_wins ?? 0;
  const bWins = s.b_wins ?? 0;
  const ties = s.ties ?? 0;
  const byDim = s.by_dimension || {};
  const diffKeys = Object.keys(detail.subject_diff || {});

  // 进行中进度取自 comparison 行的 total_cases/done_cases（summary 仅在完成时才写）。
  const totalCases = detail.total_cases || 0;
  const doneCases = detail.done_cases || 0;
  const pct = totalCases ? Math.round((doneCases / totalCases) * 100) : 0;

  const matchesConclusion = (v: PairwiseCaseVerdict) =>
    !conclusionFilter || v.winner === conclusionFilter;
  const matchesConfidence = (v: PairwiseCaseVerdict) =>
    !confidenceFilter || v.confidence_kind === confidenceFilter;
  const filtered: PairwiseCaseVerdict[] = (detail.verdicts || []).filter(
    (v) => matchesConclusion(v) && matchesConfidence(v)
  );

  const hasActiveFilters = Boolean(conclusionFilter || confidenceFilter);
  const resetFilters = () => {
    setConclusionFilter(undefined);
    setConfidenceFilter(undefined);
  };

  const orderSensitiveN = s.order_sensitive_count ?? 0;
  const safetyDoubtN = s.safety_doubt_count ?? 0;
  const humanCalibratedN = s.human_calibrated_count ?? 0;

  const runAName = detail.run_a_name || `运行 #${detail.run_a_id}`;
  const runBName = detail.run_b_name || `运行 #${detail.run_b_id}`;

  const overall = s.overall_winner;
  const conclusion =
    overall === "B"
      ? `${runBName} 整体更优`
      : overall === "A"
      ? `${runAName} 整体更优（本次相对回退）`
      : "两次评测整体持平";

  return (
    <Space direction="vertical" size={16} style={{ display: "flex" }}>
      {detail.status === "running" && (
        <Card className="pw-running" styles={{ body: { padding: 20 } }}>
          <div className="pw-running__head">
            <Spin indicator={<LoadingOutlined style={{ fontSize: 20 }} spin />} />
            <div className="pw-running__meta">
              <div className="pw-running__title">逐题对比进行中</div>
              <div className="pw-running__sub">
                B({runBName}) vs A({runAName}) · 裁判 {detail.judge_model}
              </div>
            </div>
            <div className="pw-running__count mono">
              {doneCases}
              <span className="pw-running__count-total"> / {totalCases || "…"}</span>
            </div>
          </div>
          <div className="pw-progress">
            <div
              className={`pw-progress__bar${totalCases ? "" : " pw-progress__bar--indeterminate"}`}
              style={totalCases ? { width: `${pct}%` } : undefined}
            />
          </div>
        </Card>
      )}
      {detail.status === "failed" && (
        <Alert type="error" showIcon message="对比失败" description={detail.error_msg} />
      )}

      {detail.status === "done" && (
        <>
      <Card>
        <Title level={4} style={{ marginTop: 0 }}>
          {conclusion}
        </Title>
        <Space size={8} wrap style={{ marginBottom: 4 }}>
          <Tag color="default">A（基线）= {runAName} · run #{detail.run_a_id}</Tag>
          <Tag color="green">B（本次）= {runBName} · run #{detail.run_b_id}</Tag>
        </Space>
        <div>
          <Text type="secondary">裁判 {detail.judge_model} · 判分尺子一致（A/B 后续均指代上述评测）</Text>
        </div>
        <Row gutter={16} style={{ marginTop: 16 }}>
          <Col><Statistic title="B 更好（改善）" value={bWins} valueStyle={{ color: "var(--primary)" }} /></Col>
          <Col><Statistic title="持平" value={ties} /></Col>
          <Col><Statistic title="A 更好（回退）" value={aWins} valueStyle={{ color: "var(--fail)" }} /></Col>
          <Col><Statistic title="B 胜率" value={total ? Math.round((bWins / total) * 100) : 0} suffix="%" /></Col>
          <Col>
            <Tooltip title="低置信：把 A/B 位置互换后两次判定不一致（结论受位置偏见影响、不稳），建议人工复核。">
              <Statistic title="低置信 · 顺序敏感" value={orderSensitiveN} valueStyle={{ color: "var(--warn)" }} />
            </Tooltip>
          </Col>
          <Col>
            <Tooltip title="低置信：两次一致倾向某方更优，但被医疗保守规则按安全维度降级为持平，建议人工复核。">
              <Statistic title="低置信 · 安全存疑" value={safetyDoubtN} valueStyle={{ color: "var(--fail)" }} />
            </Tooltip>
          </Col>
          <Col>
            <Tooltip title="已由人工覆写结论/维度/理由，报告统计按校准值计算。">
              <Statistic title="人工校准" value={humanCalibratedN} valueStyle={{ color: "var(--primary)" }} />
            </Tooltip>
          </Col>
        </Row>
        {diffKeys.length > 0 && (
          <div style={{ marginTop: 12 }}>
            <Text type="secondary">被测差异：</Text>{" "}
            {diffKeys.map((k) => (
              <Tag key={k} color="blue">{k}</Tag>
            ))}
          </div>
        )}
      </Card>

      <Row gutter={16}>
        {["safety", "function", "experience"].map((dim) => {
          const d = byDim[dim] || { A: 0, B: 0, tie: 0 };
          return (
            <Col span={8} key={dim}>
              <Card size="small" title={`${DIM_LABEL[dim]}维度`}>
                <Space size={16}>
                  <Statistic title="B 胜" value={d.B} valueStyle={{ color: "var(--primary)" }} />
                  <Statistic title="平" value={d.tie} />
                  <Statistic title="A 胜" value={d.A} valueStyle={{ color: "var(--fail)" }} />
                </Space>
              </Card>
            </Col>
          );
        })}
      </Row>

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
          pagination={{ pageSize: 20, current: tablePage, onChange: (p) => setTablePage(p) }}
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
            { title: "结论", render: (_, r) => verdictTag(r) },
            {
              title: <HeaderHint label="置信" hint={CONFIDENCE_HINT} />,
              dataIndex: "confidence",
              render: (_: string, r) => confidenceTag(r),
            },
            {
              title: <HeaderHint label="维度" hint={DIMENSION_HINT} />,
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
              render: (_, r) => {
                const sensitive =
                  !r.human_calibrated &&
                  r.confidence_kind === "order" &&
                  r.winner === "tie";
                const runs = r.order_runs || [];
                if (sensitive && runs.length === 2) {
                  const phrase = (w: string) =>
                    w === "A" ? "判 A 更优" : w === "B" ? "判 B 更优" : "判持平";
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
                return r.reason;
              },
            },
          ]}
          expandable={{
            expandedRowKeys: expandedKeys,
            onExpandedRowsChange: (keys) => setExpandedKeys(keys as string[]),
            expandedRowRender: (r) => (
              <Row gutter={12}>
                <Col span={12}>
                  <ConversationCol
                    runId={detail.run_a_id}
                    sampleId={r.sample_id}
                    side="A"
                    runName={runAName}
                    comparisonId={id}
                  />
                </Col>
                <Col span={12}>
                  <ConversationCol
                    runId={detail.run_b_id}
                    sampleId={r.sample_id}
                    side="B"
                    runName={runBName}
                    comparisonId={id}
                  />
                </Col>
              </Row>
            ),
          }}
        />
      </Card>
        </>
      )}

      <PairwiseCalibrateModal
        open={calibrateVerdict != null}
        comparisonId={id}
        verdict={calibrateVerdict}
        onClose={() => setCalibrateVerdict(null)}
        onSaved={load}
      />
    </Space>
  );
}
