import {
  Alert,
  Button,
  Card,
  Input,
  Segmented,
  Select,
  Space,
  Tag,
  Tooltip,
  Typography,
} from "antd";
import { QuestionCircleOutlined, SwapOutlined } from "@ant-design/icons";
import { PAIRWISE_SUBJECT_LABELS, type usePairwisePage } from "../hooks/usePairwisePage";

const { Text } = Typography;

type PairwisePageState = ReturnType<typeof usePairwisePage>;

export function PairwiseCreateCard({
  runOptions,
  judgeModels,
  runA,
  setRunA,
  runB,
  setRunB,
  judgeId,
  setJudgeId,
  scope,
  setScope,
  note,
  setNote,
  check,
  diffKeys,
  canSubmit,
  submitting,
  onSubmit,
}: Pick<
  PairwisePageState,
  | "runOptions"
  | "judgeModels"
  | "runA"
  | "setRunA"
  | "runB"
  | "setRunB"
  | "judgeId"
  | "setJudgeId"
  | "scope"
  | "setScope"
  | "note"
  | "setNote"
  | "check"
  | "diffKeys"
  | "canSubmit"
  | "submitting"
  | "onSubmit"
  | "judgeModels"
>) {
  return (
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
            <Text type="secondary" style={{ fontSize: 12 }}>
              A · 基线评测
            </Text>
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
            <Text type="secondary" style={{ fontSize: 12 }}>
              B · 本次评测
            </Text>
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
            <Text type="secondary" style={{ fontSize: 12 }}>
              裁判模型
            </Text>
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
          <Text type="secondary" style={{ fontSize: 12 }}>
            描述（本次对比目的，可选）
          </Text>
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
                  要公平比出谁更好，两次评测必须用<b>同一把判分尺子</b>
                  （判分标准、算分口径完全一致），只允许被测的 bot 不一样。下面这些得先消除：
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
                  <Tag key={k}>{PAIRWISE_SUBJECT_LABELS[k] || k}</Tag>
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
  );
}
