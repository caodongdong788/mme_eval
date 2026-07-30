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
import { CxReplayEmbed } from "./CxReplayEmbed";
import { PairwiseConfidenceTag, PairwiseVerdictTag } from "./PairwiseVerdictTags";

const { Paragraph, Text } = Typography;

const SIDE_OPTIONS = [
  { value: "A", label: "A 更好" },
  { value: "B", label: "B 更好" },
  { value: "tie", label: "持平" },
];

function DimensionVerdictTags({ dimensions }: { dimensions: Record<string, string> }) {
  return (
    <Space size={[4, 4]} wrap>
      {EVALUATION_DIMENSIONS.map((dimension) => {
        const winner = dimensions[dimension] || "tie";
        const label = winner === "A" ? "A 更好" : winner === "B" ? "B 更好" : "持平";
        return (
          <Tag key={dimension} color={winner === "B" ? "green" : winner === "A" ? "default" : undefined}>
            {DIM_LABEL[dimension]}：{label}
          </Tag>
        );
      })}
    </Space>
  );
}

function DimensionDecisionSummary({ verdict }: { verdict: PairwiseCaseVerdict }) {
  const dimensions = verdict.dimension_winners || {};
  const aCount = EVALUATION_DIMENSIONS.filter((dimension) => dimensions[dimension] === "A").length;
  const bCount = EVALUATION_DIMENSIONS.filter((dimension) => dimensions[dimension] === "B").length;
  const tieCount = EVALUATION_DIMENSIONS.length - aCount - bCount;
  const safetyWinner = dimensions.medical_safety;
  const overall = verdict.winner === "A" ? "A 更好" : verdict.winner === "B" ? "B 更好" : "持平";
  const rule = safetyWinner === "A" || safetyWinner === "B"
    ? `医学安全性由 ${safetyWinner} 胜出，安全优先，因此总胜方为 ${overall}`
    : `A 胜 ${aCount} 项、B 胜 ${bCount} 项、持平 ${tieCount} 项，因此总胜方为 ${overall}`;
  return (
    <div className="pairwise-order-resolution">
      <Text strong>有效八维结论（用于决定总胜方）</Text>
      <DimensionVerdictTags dimensions={dimensions} />
      <Text type="secondary">{rule}</Text>
    </div>
  );
}

function VerdictReason({ verdict }: { verdict: PairwiseCaseVerdict }) {
  const orderSensitive =
    !verdict.human_calibrated && verdict.confidence_kind === "order";
  const attempts = verdict.order_runs || [];
  const hasDimensionTrace = attempts.some((attempt) => Object.keys(attempt.dimension_winners || {}).length > 0);
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
              {attempt.dimension_winners && Object.keys(attempt.dimension_winners).length > 0 && (
                <div className="pairwise-order-attempt__dimensions">
                  <Text type="secondary">本次八维判断</Text>
                  <DimensionVerdictTags dimensions={attempt.dimension_winners} />
                </div>
              )}
            </div>
          ))}
          {hasDimensionTrace ? (
            <>
              <DimensionDecisionSummary verdict={verdict} />
              <Text type="secondary">
                同一维度若两次分别判 A、B 胜出，则该维度按持平处理；一胜一持平会保留胜方，但标记为低置信。
              </Text>
            </>
          ) : (
            <Alert
              type="warning"
              showIcon
              message="历史对比未保存单次八维判定"
              description="不能从文字理由反推正式维度结论；重新发起该 Pairwise 对比后会展示两次换序的八维依据。"
            />
          )}
          <Text type="secondary">
            两次 Judge 的整体判断不一致；平台已按八维结果计算总胜方，并标记为顺序敏感，建议人工复核。
          </Text>
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
  replayUrl,
}: {
  side: "A" | "B";
  runId: number;
  runName: string;
  sampleId: string;
  comparisonId: number;
  messages: Parameters<typeof ConversationThread>[0]["messages"];
  replayUrl?: string;
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
        {replayUrl ? (
          <CxReplayEmbed
            src={replayUrl}
            messages={messages}
            resolveImageSrc={(imagePath) =>
              `/api/runs/${runId}/cases/${encodeURIComponent(sampleId)}/images/${encodeURIComponent(imagePath)}`
            }
          />
        ) : messages.length ? (
          <ConversationThread messages={messages} maxHeight={620} />
        ) : (
          <Empty description="暂无对话数据" />
        )}
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
  const { messagesA, messagesB, replayUrlA, replayUrlB } = usePairwiseExpandedMessages(
    runAId,
    runBId,
    sampleId
  );

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
            replayUrl={replayUrlA}
          />
          <ConversationColumn
            side="B"
            runId={runBId}
            runName={runBName}
            sampleId={verdict.sample_id}
            comparisonId={comparisonId}
            messages={messagesB}
            replayUrl={replayUrlB}
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
                <Text strong>人工校准（下方默认值为机器有效结论）</Text>
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
