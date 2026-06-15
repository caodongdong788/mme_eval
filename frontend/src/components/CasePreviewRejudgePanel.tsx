import { Alert, Button, Descriptions, Space } from "antd";
import type { PreviewRejudgeResult } from "../api/index";

export function CasePreviewRejudgePanel({
  previewing,
  yamlLoading,
  yamlText,
  previewResult,
  onPreview,
}: {
  previewing: boolean;
  yamlLoading: boolean;
  yamlText: string;
  previewResult: PreviewRejudgeResult | null;
  onPreview: () => void;
}) {
  return (
    <Space direction="vertical" size={10} style={{ width: "100%" }}>
      <Button
        type="primary"
        size="large"
        block
        loading={previewing}
        onClick={onPreview}
        disabled={yamlLoading || !yamlText}
      >
        试判此用例（预览）
      </Button>
      <span style={{ fontSize: 12, color: "var(--muted)" }}>
        用编辑后的判据跑一次试判，仅预览、不修改当前 run；满意后点右上「覆盖当前 benchmark」。
      </span>
      {previewResult && (
        <Alert
          type={previewResult.changed ? "warning" : "success"}
          showIcon
          message={previewResult.changed ? "试判结果与当前不同" : "试判结果与当前一致"}
          description={
            <Space direction="vertical" size={8} style={{ width: "100%", marginTop: 4 }}>
              <Descriptions column={1} size="small">
                <Descriptions.Item label="上线判定">
                  {previewResult.current.release_passed ? "通过" : "失败"}
                  {" → "}
                  {previewResult.preview.release_passed ? (
                    <span className="status-dot status-dot--pass">通过</span>
                  ) : (
                    <span className="status-dot status-dot--fail">失败</span>
                  )}
                </Descriptions.Item>
                <Descriptions.Item label="综合分">
                  {previewResult.current.composite_score?.toFixed?.(2) ?? "-"}
                  {" → "}
                  {previewResult.preview.composite_score?.toFixed?.(2) ?? "-"}
                </Descriptions.Item>
                <Descriptions.Item label="评级">
                  {previewResult.current.grade || "-"}
                  {" → "}
                  {previewResult.preview.grade || "-"}
                </Descriptions.Item>
                <Descriptions.Item label="硬门槛">
                  {previewResult.current.hard_gate_passed ? "通过" : "失败"}
                  {" → "}
                  {previewResult.preview.hard_gate_passed ? "通过" : "失败"}
                </Descriptions.Item>
              </Descriptions>
              <div>
                <strong style={{ fontSize: 12 }}>本次扣分项</strong>
                {previewResult.preview.score_deductions.length === 0 ? (
                  <span style={{ fontSize: 12, marginLeft: 8, color: "var(--muted)" }}>
                    无扣分
                  </span>
                ) : (
                  <ul style={{ margin: "4px 0 0", paddingLeft: 18 }}>
                    {previewResult.preview.score_deductions.map((d, i) => (
                      <li key={i} style={{ fontSize: 12 }}>
                        {d}
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            </Space>
          }
        />
      )}
    </Space>
  );
}
