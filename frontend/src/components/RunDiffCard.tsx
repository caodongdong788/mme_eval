import { Alert, Card, Select, Space, Tag } from "antd";
import { RunDiff, RunSummary } from "../api/index";

export interface RunDiffCardProps {
  otherRuns: RunSummary[];
  diff: RunDiff | null;
  onSelectBaseline: (runId: number) => void;
}

export function RunDiffCard({ otherRuns, diff, onSelectBaseline }: RunDiffCardProps) {
  return (
    <Card title="与历史 run 对比" size="small">
      <Space direction="vertical" style={{ width: "100%" }}>
        <Select
          placeholder="选择一个历史 run 作为对比基线"
          style={{ width: 360 }}
          options={otherRuns.map((r) => ({ value: r.id, label: `#${r.id} ${r.name || r.run_slug}` }))}
          onChange={(v) => onSelectBaseline(v)}
        />
        {diff && (
          <>
            <Alert
              type={diff.pass_rate_delta >= 0 ? "success" : "warning"}
              message={`通过率变化：${(diff.pass_rate_delta * 100).toFixed(1)}% ｜ 回归 ${diff.regressions.length} 例 ｜ 改善 ${diff.improvements.length} 例 ｜ 判分逻辑${diff.judge_logic_changed ? "已变更" : "未变"}`}
            />
            {diff.regressions.length > 0 && (
              <div>
                回归用例：
                {diff.regressions.map((s) => (
                  <Tag key={s} color="red">
                    {s}
                  </Tag>
                ))}
              </div>
            )}
          </>
        )}
      </Space>
    </Card>
  );
}
