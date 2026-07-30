import { useEffect, useState } from "react";
import {
  Alert,
  Button,
  Drawer,
  Empty,
  Form,
  Input,
  Popconfirm,
  Radio,
  Select,
  Space,
  Tag,
  Typography,
  message,
} from "antd";
import { ArrowRightOutlined, ReloadOutlined, SaveOutlined } from "@ant-design/icons";
import { Link } from "react-router-dom";
import { api, type PairwiseCalibratePayload, type PairwiseCaseVerdict } from "../api/index";
import { DIM_LABEL, EVALUATION_DIMENSIONS } from "../labels";
import { usePairwiseExpandedMessages } from "../hooks/usePairwiseExpandedMessages";
import { formatApiError } from "../utils/apiError";
import { ConversationThread } from "./ConversationThread";
import { PairwiseConfidenceTag, PairwiseVerdictTag } from "./PairwiseVerdictTags";

const { Paragraph, Text } = Typography;

const SIDE_OPTIONS = [
  { value: "A", label: "A 更好" },
  { value: "B", label: "B 更好" },
  { value: "tie", label: "持平" },
];

function VerdictReason({ verdict }: { verdict: PairwiseCaseVerdict }) {
  const orderSensitive =
    !verdict.human_calibrated && verdict.confidence_kind === "order" && verdict.winner === "tie";
  const attempts = verdict.order_runs || [];
  const winnerLabel = (winner: string) =>
    winner === "A" ? "A 更好" : winner === "B" ? "B 更好" : "持平";

  return (
    <div className="pairwise-detail-reason">
      <div className="pairwise-detail-reason__head">
        <Text strong>Judge 判定理由</Text>
        <Space size={4} wrap>
          <PairwiseVerdictTag verdict={verdict} />
          <PairwiseConfidenceTag verdict={verdict} />
        </Space>
      </div>
      {orderSensitive && attempts.length === 2 ? (
        <div className="pairwise-order-attempts">
          {attempts.map((attempt, index) => (
            <div key={index} className="pairwise-order-attempt">
              <Tag color={index === 0 ? "default" : "green"}>
                顺序{index + 1} · 上方={attempt.top}
              </Tag>
              <Text strong>{winnerLabel(attempt.winner)}</Text>
              <Paragraph>{attempt.reason || "未提供理由"}</Paragraph>
            </div>
          ))}
          <Text type="secondary">两次顺序判定不一致，系统按持平处理，建议人工校准。</Text>
        </div>
      ) : (
        <Paragraph className="pairwise-detail-reason__content">{verdict.reason || "未提供理由"}</Paragraph>
      )}
    </div>
  );
}

function ConversationColumn({
  side,
  runId,
  runName,
  sampleId,
  comparisonId,
  messages,
}: {
  side: "A" | "B";
  runId: number;
  runName: string;
  sampleId: string;
  comparisonId: number;
  messages: Parameters<typeof ConversationThread>[0]["messages"];
}) {
  return (
    <section className="pairwise-detail-conversation">
      <div className="pairwise-detail-conversation__head">
        <div>
          <Tag color={side === "B" ? "green" : "default"}>{side === "A" ? "A · 基线" : "B · 本次"}</Tag>
          <Text strong>{runName}</Text>
        </div>
        <Link
          to={`/runs/${runId}/cases/${encodeURIComponent(sampleId)}`}
          state={{
            from: {
              to: `/pairwise/${comparisonId}`,
              state: { expandedKey: sampleId },
              label: "Pairwise 对比",
            },
          }}
        >
          用例明细 <ArrowRightOutlined />
        </Link>
      </div>
      <div className="pairwise-detail-conversation__body">
        {messages.length ? <ConversationThread messages={messages} maxHeight={620} /> : <Empty description="暂无对话数据" />}
      </div>
    </section>
  );
}

export function PairwiseCaseDetailDrawer({
  open,
  verdict,
  comparisonId,
  runAId,
  runBId,
  runAName,
  runBName,
  onClose,
  onSaved,
}: {
  open: boolean;
  verdict: PairwiseCaseVerdict | null;
  comparisonId: number;
  runAId: number;
  runBId: number;
  runAName: string;
  runBName: string;
  onClose: () => void;
  onSaved: () => void;
}) {
  const [form] = Form.useForm<PairwiseCalibratePayload>();
  const [saving, setSaving] = useState(false);
  const sampleId = verdict?.sample_id || "";
  const { messagesA, messagesB } = usePairwiseExpandedMessages(runAId, runBId, sampleId);

  useEffect(() => {
    if (!open || !verdict) return;
    form.setFieldsValue({
      winner: verdict.winner,
      reason: verdict.reason,
      dimension_winners: Object.fromEntries(
        EVALUATION_DIMENSIONS.map((dimension) => [
          dimension,
          (verdict.dimension_winners?.[dimension] as "A" | "B" | "tie") || "tie",
        ]),
      ),
    });
  }, [form, open, verdict]);

  const save = async () => {
    if (!verdict) return;
    try {
      const value = await form.validateFields();
      setSaving(true);
      await api.calibratePairwiseVerdict(comparisonId, verdict.sample_id, {
        winner: value.winner,
        reason: (value.reason || "").trim(),
        dimension_winners: value.dimension_winners || {},
      });
      message.success("已保存人工校准，汇总已更新");
      onSaved();
      onClose();
    } catch (error: unknown) {
      if (error && typeof error === "object" && "errorFields" in error) return;
      message.error(formatApiError(error, "保存校准失败"));
    } finally {
      setSaving(false);
    }
  };

  const resetMachine = async () => {
    if (!verdict) return;
    try {
      setSaving(true);
      await api.resetPairwiseCalibration(comparisonId, verdict.sample_id);
      message.success("已恢复机器判定");
      onSaved();
      onClose();
    } catch (error: unknown) {
      message.error(formatApiError(error, "恢复失败"));
    } finally {
      setSaving(false);
    }
  };

  const title = verdict?.sub_scenario || verdict?.scenario || verdict?.sample_id || "用例对比明细";
  return (
    <Drawer
      className="pairwise-case-drawer"
      title={<span>用例对比明细 · {title}</span>}
      open={open}
      onClose={onClose}
      width="min(1480px, calc(100vw - 48px))"
      destroyOnClose
      extra={
        <Button type="primary" icon={<SaveOutlined />} loading={saving} onClick={save}>
          保存校准
        </Button>
      }
    >
      {verdict && (
        <div className="pairwise-detail-grid">
          <ConversationColumn
            side="A"
            runId={runAId}
            runName={runAName}
            sampleId={verdict.sample_id}
            comparisonId={comparisonId}
            messages={messagesA}
          />
          <ConversationColumn
            side="B"
            runId={runBId}
            runName={runBName}
            sampleId={verdict.sample_id}
            comparisonId={comparisonId}
            messages={messagesB}
          />
          <aside className="pairwise-detail-judge">
            {verdict.human_calibrated && verdict.auto_winner != null && (
              <Alert
                type="info"
                showIcon
                message={`机器原判：${verdict.auto_winner === "A" ? "A 更好" : verdict.auto_winner === "B" ? "B 更好" : "持平"}`}
                description={verdict.auto_reason || undefined}
              />
            )}
            <VerdictReason verdict={verdict} />
            <div className="pairwise-calibration">
              <div className="pairwise-calibration__head">
                <Text strong>人工校准</Text>
                <Text type="secondary">保存后覆盖有效结论并重算汇总</Text>
              </div>
              <Form form={form} layout="vertical" requiredMark={false}>
                <Form.Item name="winner" label="结论" rules={[{ required: true, message: "请选择结论" }]}>
                  <Radio.Group optionType="button" buttonStyle="solid" options={SIDE_OPTIONS} />
                </Form.Item>
                <div className="pairwise-calibration__dimensions">
                  {EVALUATION_DIMENSIONS.map((dimension) => (
                    <Form.Item
                      key={dimension}
                      name={["dimension_winners", dimension]}
                      label={DIM_LABEL[dimension]}
                    >
                      <Select size="small" options={SIDE_OPTIONS} />
                    </Form.Item>
                  ))}
                </div>
                <Form.Item name="reason" label="人工校准理由">
                  <Input.TextArea
                    placeholder="补充本次校准依据（可选）"
                    autoSize={{ minRows: 3, maxRows: 6 }}
                    maxLength={500}
                    showCount
                  />
                </Form.Item>
                <Space wrap>
                  <Button type="primary" icon={<SaveOutlined />} loading={saving} onClick={save}>
                    保存校准
                  </Button>
                  {verdict.human_calibrated && (
                    <Popconfirm title="确认恢复机器判定？" onConfirm={resetMachine} okText="恢复" cancelText="取消">
                      <Button icon={<ReloadOutlined />} loading={saving}>恢复机器判定</Button>
                    </Popconfirm>
                  )}
                </Space>
              </Form>
            </div>
          </aside>
        </div>
      )}
    </Drawer>
  );
}
