import { List, Tag, Typography } from "antd";
import { DIM_LABEL } from "../labels";
import { DashPanel } from "./DashPanel";

type CaseData = Record<string, unknown>;

interface ReferenceAnswerEntry {
  key: string;
  label: string;
  answers: string[];
}

function record(value: unknown): CaseData {
  return value && typeof value === "object" && !Array.isArray(value)
    ? value as CaseData
    : {};
}

function answers(value: unknown): string[] {
  const values = Array.isArray(value) ? value : value ? [value] : [];
  return values.map(String).map((item) => item.trim()).filter(Boolean);
}

function dimensionLabel(value: unknown): string {
  const key = String(value || "");
  return DIM_LABEL[key as keyof typeof DIM_LABEL] || key || "未绑定维度";
}

export function referenceAnswerEntries(evaluation: unknown): ReferenceAnswerEntry[] {
  const data = record(evaluation);
  const dimensions = record(data.dimension_criteria);
  const entries: ReferenceAnswerEntry[] = [];

  Object.entries(dimensions).forEach(([dimension, value]) => {
    const details = record(value);
    const referenceAnswers = answers(details.reference_answers);
    if (referenceAnswers.length) {
      entries.push({
        key: `dimension-${dimension}`,
        label: `八维 · ${dimensionLabel(dimension)}`,
        answers: referenceAnswers,
      });
    }
  });

  const guidelines = Array.isArray(data.guidelines) ? data.guidelines : [];
  guidelines.forEach((value, index) => {
    const guideline = record(value);
    const referenceAnswers = answers(guideline.reference_answers);
    if (referenceAnswers.length) {
      entries.push({
        key: `guideline-${String(guideline.id || index)}`,
        label: `指南 ${String(guideline.id || index + 1)} · ${dimensionLabel(guideline.dimension)}`,
        answers: referenceAnswers,
      });
    }
  });
  return entries;
}

export function ReferenceAnswersPanel({ evaluation }: { evaluation: unknown }) {
  const entries = referenceAnswerEntries(evaluation);
  if (!entries.length) return null;
  return (
    <DashPanel
      title="好答案参考"
      extra={<Tag color="purple">{entries.length} 项</Tag>}
      bodyClassName="dash-panel__body--flush"
    >
      <div className="reference-answers-panel">
        <Typography.Paragraph type="secondary" className="reference-answers-panel__hint">
          来自该次评测冻结的 Benchmark Case，仅作理想回答参考，不要求逐字一致。
        </Typography.Paragraph>
        <List
          dataSource={entries}
          renderItem={(entry) => (
            <List.Item>
              <div className="reference-answers-panel__entry">
                <Typography.Text strong>{entry.label}</Typography.Text>
                <ol>
                  {entry.answers.map((answer, index) => <li key={`${entry.key}-${index}`}>{answer}</li>)}
                </ol>
              </div>
            </List.Item>
          )}
        />
      </div>
    </DashPanel>
  );
}
