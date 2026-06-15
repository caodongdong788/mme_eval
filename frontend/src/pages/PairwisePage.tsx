import { useCallback, useEffect, useMemo, useState } from "react";
import {
  Alert,
  Button,
  Card,
  Input,
  Popconfirm,
  Progress,
  Segmented,
  Select,
  Space,
  Table,
  Tag,
  Tooltip,
  Typography,
  message,
} from "antd";
import { QuestionCircleOutlined } from "@ant-design/icons";
import { SwapOutlined } from "@ant-design/icons";
import { useNavigate } from "react-router-dom";
import {
  api,
  type JudgeModel,
  type PairwiseComparability,
  type PairwiseComparison,
  type RunSummary,
} from "../api";
import { formatApiError } from "../utils/apiError";

const { Text } = Typography;

function runLabel(r: RunSummary): string {
  return `#${r.id} · ${r.name}`;
}

export default function PairwisePage() {
  const navigate = useNavigate();
  const [runs, setRuns] = useState<RunSummary[]>([]);
  const [judgeModels, setJudgeModels] = useState<JudgeModel[]>([]);
  const [history, setHistory] = useState<PairwiseComparison[]>([]);
  const [runA, setRunA] = useState<number>();
  const [runB, setRunB] = useState<number>();
  const [judgeId, setJudgeId] = useState<number>();
  const [scope, setScope] = useState<"all" | "divergent_only">("all");
  const [note, setNote] = useState("");
  const [check, setCheck] = useState<PairwiseComparability | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const loadHistory = useCallback(() => {
    api.listPairwise().then(setHistory).catch(() => {});
  }, []);

  useEffect(() => {
    api.listRuns().then((rs) => setRuns(rs.filter((r) => r.status === "success")));
    api.listJudgeModels().then(setJudgeModels);
    loadHistory();
  }, [loadHistory]);

  // 有进行中的对比时轮询刷新历史列表（页面不可见时暂停）；全部结束自动停。
  const anyRunning = history.some((h) => h.status === "running");
  useEffect(() => {
    if (!anyRunning) return;
    const t = window.setInterval(() => {
      if (document.visibilityState === "visible") loadHistory();
    }, 2500);
    return () => window.clearInterval(t);
  }, [anyRunning, loadHistory]);

  // 选定两个 run 后做可比性预检（只卡判分尺子、放开被测 bot）。
  useEffect(() => {
    if (runA && runB && runA !== runB) {
      api.precheckPairwise(runA, runB).then(setCheck).catch(() => setCheck(null));
    } else {
      setCheck(null);
    }
  }, [runA, runB]);

  const runOptions = useMemo(
    () => runs.map((r) => ({ value: r.id, label: runLabel(r), disabled: !r.has_traces })),
    [runs]
  );

  const canSubmit = Boolean(runA && runB && judgeId && check?.comparable);

  const onSubmit = async () => {
    if (!runA || !runB || !judgeId) return;
    setSubmitting(true);
    try {
      await api.createPairwise({
        run_a_id: runA,
        run_b_id: runB,
        judge_model_id: judgeId,
        scope,
        note: note.trim() || undefined,
      });
      message.success("已发起对比，进度见下方历史列表");
      setNote(""); // 清空描述，便于发起下一次
      loadHistory(); // 立即新增一条进行中的记录，进度落在状态列
    } catch (e: any) {
      message.error(formatApiError(e, "发起对比失败"));
    } finally {
      setSubmitting(false);
    }
  };

  const saveNote = async (id: number, value: string) => {
    const next = value.trim();
    try {
      await api.updatePairwiseNote(id, next);
      setHistory((h) => h.map((x) => (x.id === id ? { ...x, note: next } : x)));
    } catch (e: any) {
      message.error(formatApiError(e, "保存备注失败"));
    }
  };

  const onDelete = async (id: number) => {
    try {
      await api.deletePairwise(id);
      message.success("已删除该对比");
      setHistory((h) => h.filter((x) => x.id !== id));
    } catch (e: any) {
      message.error(formatApiError(e, "删除失败"));
    }
  };

  const subjectDiff = check?.subject_diff || {};
  const diffKeys = Object.keys(subjectDiff);
  const SUBJECT_LABELS: Record<string, string> = {
    model: "被测模型",
    base_url: "服务地址",
    system_prompt: "系统提示",
    adapter_type: "适配器类型",
  };

  return (
    <Space direction="vertical" size={16} style={{ display: "flex" }}>
      <Card
        title={
          <Space>
            <SwapOutlined />
            <span>Pairwise 对比 · 同一裁判逐题 PK 两次评测</span>
          </Space>
        }
      >
        <Space direction="vertical" size={12} style={{ display: "flex" }}>
          <Space wrap size={12} align="start">
            <div>
              <Text type="secondary" style={{ fontSize: 12 }}>A · 基线评测</Text>
              <br />
              <Select
                style={{ width: 320 }}
                placeholder="选择基线 run"
                options={runOptions}
                value={runA}
                onChange={setRunA}
                showSearch
                optionFilterProp="label"
              />
            </div>
            <div>
              <Text type="secondary" style={{ fontSize: 12 }}>B · 本次评测</Text>
              <br />
              <Select
                style={{ width: 320 }}
                placeholder="选择本次 run"
                options={runOptions}
                value={runB}
                onChange={setRunB}
                showSearch
                optionFilterProp="label"
              />
            </div>
            <div>
              <Text type="secondary" style={{ fontSize: 12 }}>裁判模型</Text>
              <br />
              <Select
                style={{ width: 240 }}
                placeholder="选择判分模型"
                options={judgeModels.map((j) => ({ value: j.id, label: `${j.name} · ${j.model}` }))}
                value={judgeId}
                onChange={setJudgeId}
              />
            </div>
            <div>
              <Text type="secondary" style={{ fontSize: 12 }}>
                对比范围{" "}
                <Tooltip title="全部=逐题对比共有用例（每题 2 次裁判调用）；仅差异用例=只对两次上线判定不同的用例对比，省成本用于快筛">
                  <QuestionCircleOutlined style={{ color: "var(--muted)" }} />
                </Tooltip>
              </Text>
              <br />
              <Segmented
                value={scope}
                onChange={(v) => setScope(v as "all" | "divergent_only")}
                options={[
                  { label: "全部用例", value: "all" },
                  { label: "仅差异用例", value: "divergent_only" },
                ]}
              />
            </div>
          </Space>

          <div>
            <Text type="secondary" style={{ fontSize: 12 }}>描述（本次对比目的，可选）</Text>
            <Input.TextArea
              value={note}
              onChange={(e) => setNote(e.target.value)}
              placeholder="如：验证 v6 prompt 收紧后安全是否退化"
              autoSize={{ minRows: 1, maxRows: 3 }}
              maxLength={500}
              showCount
              style={{ marginTop: 4 }}
            />
          </div>

          {check && !check.comparable && (
            <Alert
              type="error"
              showIcon
              message="这两次评测没法公平对比"
              description={
                <>
                  <div style={{ marginBottom: 6 }}>
                    要公平比出谁更好，两次评测必须用<b>同一把判分尺子</b>（判分标准、算分口径完全一致），只允许被测的 bot 不一样。下面这些得先消除：
                  </div>
                  <ul style={{ margin: 0, paddingLeft: 18 }}>
                    {check.reasons.map((r, i) => (
                      <li key={i}>{r}</li>
                    ))}
                  </ul>
                  <div style={{ marginTop: 6, color: "var(--muted)" }}>
                    办法：选两次判分标准相同的评测；或对其中一次做「离线重判」，用同一套标准重跑后再来对比。
                  </div>
                </>
              }
            />
          )}
          {check?.comparable && diffKeys.length > 0 && (
            <Alert
              type="info"
              showIcon
              message="可以对比：两次用的是同一把判分尺子"
              description={
                <Space wrap align="center">
                  <span style={{ color: "var(--ink-secondary)" }}>仅被测 bot 不同：</span>
                  {diffKeys.map((k) => (
                    <Tag key={k}>{SUBJECT_LABELS[k] || k}</Tag>
                  ))}
                </Space>
              }
            />
          )}
          {check?.comparable && diffKeys.length === 0 && (
            <Alert type="success" showIcon message="可以对比：判分尺子一致，且被测参数也完全相同" />
          )}

          <Button type="primary" disabled={!canSubmit} loading={submitting} onClick={onSubmit}>
            发起对比
          </Button>
        </Space>
      </Card>

      <Card title="历史对比">
        <Table<PairwiseComparison>
          rowKey="id"
          dataSource={history}
          size="small"
          pagination={{ pageSize: 10 }}
          columns={[
            { title: "ID", dataIndex: "id", width: 70 },
            {
              title: "A vs B",
              render: (_, r) => (
                <Tooltip
                  title={`A=${r.run_a_name || "#" + r.run_a_id} · B=${
                    r.run_b_name || "#" + r.run_b_id
                  }`}
                >
                  <Text className="mono">#{r.run_a_id} vs #{r.run_b_id}</Text>
                </Tooltip>
              ),
            },
            { title: "裁判", dataIndex: "judge_model" },
            {
              title: "描述",
              width: 240,
              render: (_, r) => (
                <Typography.Paragraph
                  style={{ margin: 0, maxWidth: 240 }}
                  type={r.note ? undefined : "secondary"}
                  editable={{
                    text: r.note || "",
                    tooltip: "编辑备注",
                    autoSize: { minRows: 1, maxRows: 4 },
                    onChange: (v) => saveNote(r.id, v),
                  }}
                >
                  {r.note || "（点击编辑添加备注）"}
                </Typography.Paragraph>
              ),
            },
            {
              title: "状态",
              dataIndex: "status",
              width: 190,
              render: (s: string, r) => {
                if (s === "running") {
                  const total = r.total_cases || 0;
                  const done = r.done_cases || 0;
                  const pct = total ? Math.round((done / total) * 100) : 0;
                  return (
                    <Space direction="vertical" size={2} style={{ minWidth: 170, display: "flex" }}>
                      <Tag color="blue">{total ? "进行中" : "准备中"}</Tag>
                      <Tooltip title={`${done}/${total || "…"}`}>
                        <Progress percent={pct} size="small" status="active" />
                      </Tooltip>
                    </Space>
                  );
                }
                const color = s === "done" ? "green" : s === "failed" ? "red" : "blue";
                const label = s === "done" ? "完成" : s === "failed" ? "失败" : "进行中";
                return <Tag color={color}>{label}</Tag>;
              },
            },
            {
              title: "结论",
              render: (_, r) => {
                if (r.status !== "done" || !r.summary?.overall_winner) return "—";
                const w = r.summary.overall_winner;
                if (w === "tie") return <Text>持平</Text>;
                const name =
                  w === "B"
                    ? r.run_b_name || "B"
                    : r.run_a_name || "A";
                return <Text>{name} 更优</Text>;
              },
            },
            {
              title: "操作",
              width: 120,
              render: (_, r) => (
                <Space size={4}>
                  <Button type="link" size="small" onClick={() => navigate(`/pairwise/${r.id}`)}>
                    查看
                  </Button>
                  <Popconfirm
                    title="确认删除该对比？"
                    description="将连带删除其逐用例结论，不可恢复。"
                    okText="删除"
                    cancelText="取消"
                    okButtonProps={{ danger: true }}
                    onConfirm={() => onDelete(r.id)}
                  >
                    <Button type="link" size="small" danger>
                      删除
                    </Button>
                  </Popconfirm>
                </Space>
              ),
            },
          ]}
        />
      </Card>
    </Space>
  );
}
