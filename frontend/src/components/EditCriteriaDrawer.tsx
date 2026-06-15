import { Alert, Button, Drawer, Form, Input, Space, Tag, Tooltip, Typography } from "antd";
import type { ReactNode } from "react";

// 编辑判据(YAML)抽屉：另存为新 benchmark / 覆盖当前 benchmark（内置不可覆盖）。
// 纯展示 + 受控输入，保存/覆盖行为由父级注入。
// benchmarkLabel：当前正在编辑/覆盖的 benchmark（`#id「名称」`），覆盖前供用户确认对象。
// slot：可选插槽（渲染在说明与名称输入之间），用例明细页用来放「试判预览」控件与结果。
export function EditCriteriaDrawer({
  open,
  loading,
  isBuiltin,
  name,
  onNameChange,
  yamlText,
  onYamlChange,
  yamlLoading,
  onClose,
  onSaveAs,
  onOverwrite,
  benchmarkLabel,
  slot,
  title = "编辑判据(YAML) → 另存新 benchmark / 覆盖当前 benchmark",
  hideAlert = false,
  hideSaveAs = false,
}: {
  open: boolean;
  loading: boolean;
  isBuiltin: boolean;
  name: string;
  onNameChange: (v: string) => void;
  yamlText: string;
  onYamlChange: (v: string) => void;
  yamlLoading: boolean;
  onClose: () => void;
  onSaveAs: () => void;
  onOverwrite: () => void;
  benchmarkLabel?: string;
  slot?: ReactNode;
  title?: string;
  // 仅覆盖模式（用例明细页）：隐藏说明 Alert / 隐藏「另存为新 benchmark」与名称输入。
  hideAlert?: boolean;
  hideSaveAs?: boolean;
}) {
  return (
    <Drawer
      title={title}
      width={760}
      open={open}
      onClose={onClose}
      extra={
        <Space>
          <Button onClick={onClose}>取消</Button>
          <Tooltip
            title={
              isBuiltin
                ? "内置 benchmark 不可覆盖，请改用「另存为新 benchmark」"
                : "用编辑后的判据就地覆盖原 benchmark"
            }
          >
            <Button danger loading={loading} disabled={isBuiltin} onClick={onOverwrite}>
              覆盖当前 benchmark
            </Button>
          </Tooltip>
          {!hideSaveAs && (
            <Button type="primary" loading={loading} onClick={onSaveAs}>
              另存为新 benchmark
            </Button>
          )}
        </Space>
      }
    >
      {benchmarkLabel ? (
        <div style={{ marginBottom: 12 }}>
          <Typography.Text type="secondary" style={{ fontSize: 12 }}>
            当前 benchmark：
          </Typography.Text>
          <Tag color="blue">{benchmarkLabel}</Tag>
        </div>
      ) : null}
      {!hideAlert && (
        <Alert
          type="info"
          showIcon
          style={{ marginBottom: 12 }}
          message="按当前过滤命中的用例完整 YAML。保存时按 sample_id 只合并判据字段（expected_behavior/hard_gates/rubric/scoring_points），turns 等不动；YAML 里 sample_id 在源集找不到的会被丢弃，未编辑的源用例原样保留。「另存」生成新 benchmark；「覆盖」就地更新原 benchmark（内置不可覆盖），仅更新判据源、不改当前 run 已存分。两者都不触发重判——要让某个 run 反映新判据需另行「重判」。"
        />
      )}
      {slot ? <div style={{ marginBottom: 12 }}>{slot}</div> : null}
      {!hideSaveAs && (
        <Form layout="vertical" size="small">
          <Form.Item label="新 benchmark 名称" required style={{ marginBottom: 12 }}>
            <Input value={name} onChange={(e) => onNameChange(e.target.value)} />
          </Form.Item>
        </Form>
      )}
      <Input.TextArea
        value={yamlText}
        onChange={(e) => onYamlChange(e.target.value)}
        placeholder={yamlLoading ? "加载用例 YAML 中…" : ""}
        autoSize={{ minRows: 18, maxRows: 40 }}
        style={{ fontFamily: "var(--font-mono)", fontSize: 12 }}
      />
    </Drawer>
  );
}
