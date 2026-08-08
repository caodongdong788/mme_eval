import {
  Button,
  Card,
  Collapse,
  Drawer,
  Input,
  InputNumber,
  message,
  Popconfirm,
  Select,
  Space,
  Spin,
  Tabs,
  Typography,
} from "antd";
import { CodeOutlined, DeleteOutlined, PlusOutlined } from "@ant-design/icons";
import { type ReactNode, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { DIM_LABEL, EVALUATION_DIMENSIONS } from "../labels";

type CaseData = Record<string, any>;
type Pair = [string, unknown];

function asText(value: unknown): string {
  if (value == null) return "";
  return typeof value === "string" ? value : JSON.stringify(value);
}

function parseText(value: string): unknown {
  const text = value.trim();
  if (!text) return "";
  if (text.startsWith("{") || text.startsWith("[")) {
    try {
      return JSON.parse(text);
    } catch {
      return value;
    }
  }
  return value;
}

function pairs(record: unknown): Pair[] {
  return record && typeof record === "object" && !Array.isArray(record)
    ? Object.entries(record as Record<string, unknown>)
    : [];
}

function MarkdownValueEditor({ value, onChange }: { value: unknown; onChange: (next: unknown) => void }) {
  const [editing, setEditing] = useState(false);
  const text = asText(value);
  if (editing) {
    return (
      <div className="case-editor-markdown-editor">
        <Input.TextArea
          aria-label="Markdown 内容"
          value={text}
          onChange={(event) => onChange(parseText(event.target.value))}
          autoSize={{ minRows: 4, maxRows: 12 }}
        />
        <Button size="small" type="link" onClick={() => setEditing(false)}>完成编辑</Button>
      </div>
    );
  }
  return (
    <div className="case-editor-markdown-value">
      <div className="case-editor-markdown-content">
        <ReactMarkdown remarkPlugins={[remarkGfm]}>{text || "暂无内容"}</ReactMarkdown>
      </div>
      <Button size="small" type="link" onClick={() => setEditing(true)}>编辑 Markdown</Button>
    </div>
  );
}

function KeyValueEditor({
  value,
  onChange,
  addText = "新增字段",
  variant = "default",
}: {
  value: Record<string, unknown>;
  onChange: (next: Record<string, unknown>) => void;
  addText?: string;
  variant?: "default" | "profile";
}) {
  const entries = pairs(value);
  const update = (index: number, key: string, nextValue: unknown) => {
    const next: Record<string, unknown> = {};
    entries.forEach(([oldKey, oldValue], entryIndex) => {
      if (entryIndex === index) next[key.trim() || "未命名字段"] = nextValue;
      else next[oldKey] = oldValue;
    });
    onChange(next);
  };
  return (
    <div className={`case-editor-kv-list case-editor-kv-list--${variant}`}>
      {entries.map(([key, entryValue], index) => (
        <div className="case-editor-pair" key={`${key}-${index}`}>
          <Input
            aria-label="字段名称"
            value={key}
            onChange={(event) => update(index, event.target.value, entryValue)}
            placeholder="字段名称"
          />
          {variant === "profile" ? (
            <Input.TextArea
              aria-label="字段内容"
              value={asText(entryValue)}
              onChange={(event) => update(index, key, parseText(event.target.value))}
              placeholder="字段内容"
              autoSize={{ minRows: 1, maxRows: 4 }}
            />
          ) : (
            <MarkdownValueEditor value={entryValue} onChange={(nextValue) => update(index, key, nextValue)} />
          )}
          <Button
            type="text"
            danger
            icon={<DeleteOutlined />}
            aria-label={`删除字段 ${key}`}
            onClick={() => onChange(Object.fromEntries(entries.filter((_, i) => i !== index)))}
          />
        </div>
      ))}
      <Button type="dashed" size="small" icon={<PlusOutlined />} onClick={() => onChange({ ...value, "": "" })}>
        {addText}
      </Button>
    </div>
  );
}

function RequirementList({ value, onChange }: { value: unknown; onChange: (next: string[]) => void }) {
  const items = Array.isArray(value) ? value.map(String) : value ? [String(value)] : [];
  return (
    <div className="case-editor-requirement-list">
      {items.map((item, index) => (
        <div className="case-editor-requirement" key={index}>
          <span className="case-editor-requirement__index">{index + 1}</span>
          <Input.TextArea
            value={item}
            placeholder="请输入该维度的要求"
            autoSize={{ minRows: 2, maxRows: 6 }}
            onChange={(event) => onChange(items.map((v, i) => (i === index ? event.target.value : v)))}
          />
          <Button type="text" danger icon={<DeleteOutlined />} aria-label="删除要求" onClick={() => onChange(items.filter((_, i) => i !== index))} />
        </div>
      ))}
      <Button type="dashed" size="small" icon={<PlusOutlined />} onClick={() => onChange([...items, ""])}>
        新增要求
      </Button>
    </div>
  );
}

function TimelineEditor({ value, onChange }: { value: unknown; onChange: (next: unknown[]) => void }) {
  const items = Array.isArray(value) ? value : [];
  return (
    <div className="case-editor-timeline-list">
      {items.map((item, index) => (
        <Card
          key={index}
          size="small"
          className="case-editor-timeline-card"
          title={<span className="case-editor-timeline-card__title"><em>事实 {String(index + 1).padStart(2, "0")}</em><strong>{item && typeof item === "object" && !Array.isArray(item) ? String((item as CaseData).label || (item as CaseData).key || "健康记录") : "健康记录"}</strong></span>}
          extra={<Button type="text" danger icon={<DeleteOutlined />} onClick={() => onChange(items.filter((_, i) => i !== index))}>删除</Button>}
        >
          {item && typeof item === "object" && !Array.isArray(item) ? (
            <KeyValueEditor value={item as Record<string, unknown>} onChange={(next) => onChange(items.map((v, i) => (i === index ? next : v)))} />
          ) : (
            <MarkdownValueEditor value={item} onChange={(next) => onChange(items.map((v, i) => (i === index ? next : v)))} />
          )}
        </Card>
      ))}
      <Button type="dashed" icon={<PlusOutlined />} onClick={() => onChange([...items, { 内容: "" }])}>新增过往事实</Button>
    </div>
  );
}

function GuidelinesEditor({ value, onChange }: { value: unknown; onChange: (next: CaseData[]) => void }) {
  const guidelines: CaseData[] = Array.isArray(value) ? value.map((item) => ({ ...(item || {}) })) : [];
  const update = (index: number, patch: CaseData) => onChange(guidelines.map((item, i) => (i === index ? { ...item, ...patch } : item)));
  return (
    <div className="case-editor-guideline-list">
      {guidelines.map((guide, index) => {
        const criterion = Array.isArray(guide.criterion) ? guide.criterion.map(String) : guide.criterion ? [String(guide.criterion)] : [];
        return (
          <Card
            key={index}
            size="small"
            className="case-editor-guideline-card"
            title={<span className="case-editor-guideline-card__title"><em>扣分项 {String(index + 1).padStart(2, "0")}</em><strong>{DIM_LABEL[guide.dimension as keyof typeof DIM_LABEL] || "请选择关联维度"}</strong></span>}
            extra={<Button type="text" danger icon={<DeleteOutlined />} onClick={() => onChange(guidelines.filter((_, i) => i !== index))}>删除</Button>}
          >
            <div className="case-editor-guide-meta">
              <label className="case-editor-input-field"><span>关联评测维度</span><Select value={guide.dimension || undefined} placeholder="请选择" options={EVALUATION_DIMENSIONS.map((dimension) => ({ value: dimension, label: DIM_LABEL[dimension] }))} onChange={(dimension) => update(index, { dimension })} /></label>
              <label className="case-editor-input-field"><span>最高扣分</span><InputNumber min={0} value={guide.max_score ?? 1} onChange={(max_score) => update(index, { max_score: max_score ?? 0 })} /></label>
            </div>
            <Typography.Text className="case-editor-field-label">扣分逻辑</Typography.Text>
            <RequirementList value={criterion} onChange={(next) => update(index, { criterion: next })} />
          </Card>
        );
      })}
      <Button
        type="dashed"
        icon={<PlusOutlined />}
        onClick={() => onChange([...guidelines, { id: `g${String(guidelines.length + 1).padStart(2, "0")}`, dimension: "professional_accuracy", criterion: [""], max_score: 1 }])}
      >
        新增指南扣分点
      </Button>
    </div>
  );
}

export function BenchmarkCaseEditorDrawer({
  open,
  loading,
  saving,
  source,
  caseFile,
  value,
  onChange,
  onClose,
  onSave,
  onDelete,
  onLoadSourceYaml,
  variant = "benchmark",
  title,
  subtitle,
  isBuiltin = false,
  benchmarkLabel,
  headerContent,
  onOverwrite,
  saveHint,
}: {
  open: boolean;
  loading: boolean;
  saving: boolean;
  source?: string;
  caseFile?: string;
  value: CaseData | null;
  onChange: (next: CaseData) => void;
  onClose: () => void;
  onSave?: () => void;
  onDelete?: () => void;
  onLoadSourceYaml?: () => Promise<string>;
  variant?: "benchmark" | "criteria";
  title?: string;
  subtitle?: string;
  isBuiltin?: boolean;
  benchmarkLabel?: string;
  headerContent?: ReactNode;
  onOverwrite?: () => void;
  saveHint?: string;
}) {
  const [sourceOpen, setSourceOpen] = useState(false);
  const [sourceLoading, setSourceLoading] = useState(false);
  const [sourceYaml, setSourceYaml] = useState("");
  const update = (patch: CaseData) => value && onChange({ ...value, ...patch });
  const initialState = (value?.initial_state || {}) as CaseData;
  const evaluation = (value?.evaluation || {}) as CaseData;
  const criteria = (evaluation.dimension_criteria || {}) as CaseData;
  const updateInitialState = (patch: CaseData) => update({ initial_state: { ...initialState, ...patch } });
  const updateEvaluation = (patch: CaseData) => update({ evaluation: { ...evaluation, ...patch } });
  const openSourceYaml = async () => {
    if (!onLoadSourceYaml) return;
    setSourceOpen(true);
    setSourceLoading(true);
    try {
      setSourceYaml(await onLoadSourceYaml());
    } catch {
      message.error("加载源 YAML 失败");
    } finally {
      setSourceLoading(false);
    }
  };

  const tabItems = value ? [
    {
      key: "basic",
      label: "基本信息",
      children: <Card className="case-editor-card" bordered={false}>
        <div className="case-editor-basic-grid">
          <label className="case-editor-input-field"><span>用例名称 / 场景</span><Input value={value.scenario || ""} onChange={(event) => update({ scenario: event.target.value })} /></label>
          <label className="case-editor-input-field"><span>用例类别</span><Input value={value.case_type || ""} onChange={(event) => update({ case_type: event.target.value })} /></label>
          <label className="case-editor-input-field"><span>问题类型</span><Input value={value.is_bug || ""} onChange={(event) => update({ is_bug: event.target.value })} /></label>
          <label className="case-editor-input-field"><span>难度级别</span><Select value={value.level || undefined} placeholder="请选择" options={["L1", "L2", "L3"].map((level) => ({ value: level, label: level }))} onChange={(level) => update({ level })} /></label>
        </div>
      </Card>,
    },
    {
      key: "context",
      label: "用户档案与过往事实",
      children: <Space direction="vertical" size={14} style={{ display: "flex" }}>
        <Card className="case-editor-card case-editor-profile-card" title="用户档案" extra={<Typography.Text type="secondary">{pairs(initialState.user_profile).length} 项</Typography.Text>} size="small">
          <Typography.Paragraph className="case-editor-section-hint">这些信息会随本次用例注入 Agent，用来检查回答是否真正结合了患者情况。</Typography.Paragraph>
          <KeyValueEditor value={(initialState.user_profile || {}) as Record<string, unknown>} onChange={(user_profile) => updateInitialState({ user_profile })} addText="添加用户档案字段" variant="profile" />
        </Card>
        <Card className="case-editor-card case-editor-timeline-section" title="过往事实（Timeline）" extra={<Typography.Text type="secondary">按事实拆分，支持任意字段</Typography.Text>} size="small">
          <Typography.Paragraph className="case-editor-section-hint">用于模拟 Agent 可读取的历史健康信息；每条事实的字段结构不受限制。</Typography.Paragraph>
          <TimelineEditor value={initialState.Timeline ?? initialState.timeline} onChange={(Timeline) => updateInitialState({ Timeline })} />
        </Card>
      </Space>,
    },
    {
      key: "conversation",
      label: `对话（${Array.isArray(value.turns) ? value.turns.length : 0}）`,
      children: <Card className="case-editor-card case-editor-conversation-section" bordered={false}>
        <Typography.Paragraph className="case-editor-section-hint">这里仅维护用户的提问，按实际出现顺序排列；Agent 回复由评测时实时生成。</Typography.Paragraph>
        <div className="case-editor-conversation-list">
          {(Array.isArray(value.turns) ? value.turns : []).map((turn: CaseData, index: number) => (
            <Card className="case-editor-turn case-editor-turn--user" key={index} size="small" title={<span className="case-editor-turn__title"><em>第 {String(index + 1).padStart(2, "0")} 问</em><strong>用户问话</strong></span>} extra={<Button type="text" danger icon={<DeleteOutlined />} onClick={() => update({ turns: value.turns.filter((_: unknown, i: number) => i !== index) })}>删除</Button>}>
              <Input.TextArea className="case-editor-turn__content" value={turn.content || ""} placeholder="请输入用户问话" autoSize={{ minRows: 3, maxRows: 10 }} onChange={(event) => update({ turns: value.turns.map((item: CaseData, i: number) => i === index ? { ...item, content: event.target.value, role: "user" } : item) })} />
              <Input className="case-editor-turn__images" value={Array.isArray(turn.images) ? turn.images.join(", ") : ""} placeholder="图片相对路径（多个路径用英文逗号分隔，可选）" onChange={(event) => update({ turns: value.turns.map((item: CaseData, i: number) => i === index ? { ...item, images: event.target.value.split(",").map((path) => path.trim()).filter(Boolean) } : item) })} />
            </Card>
          ))}
          <Button type="dashed" icon={<PlusOutlined />} onClick={() => update({ turns: [...(Array.isArray(value.turns) ? value.turns : []), { role: "user", content: "", images: [] }] })}>新增用户问话</Button>
        </div>
      </Card>,
    },
    {
      key: "criteria",
      label: "八维评测要求",
      children: <Card className="case-editor-card case-editor-criteria-section" bordered={false}>
        <Typography.Paragraph className="case-editor-section-hint">八个维度独立评分。每条要求都会进入对应角色的 Judge 提示词。</Typography.Paragraph>
        <Collapse className="case-editor-dimension-collapse" items={EVALUATION_DIMENSIONS.map((dimension, index) => ({ key: dimension, label: <span className="case-editor-dimension-title"><em>{String(index + 1).padStart(2, "0")}</em><span><strong>{DIM_LABEL[dimension]}</strong><small>{Array.isArray(criteria[dimension]) ? `${criteria[dimension].length} 条要求` : "尚未配置要求"}</small></span></span>, children: <RequirementList value={criteria[dimension]} onChange={(requirements) => updateEvaluation({ dimension_criteria: { ...criteria, [dimension]: requirements } })} /> }))} />
      </Card>,
    },
    {
      key: "guidelines",
      label: `指南扣分点（${Array.isArray(evaluation.guidelines) ? evaluation.guidelines.length : 0}）`,
      children: <Card className="case-editor-card case-editor-guideline-section" bordered={false}>
        <Typography.Paragraph className="case-editor-section-hint">每条规则关联一个评测维度；满足触发条件后，Judge 才会依据规则检查并扣分。</Typography.Paragraph>
        <GuidelinesEditor value={evaluation.guidelines} onChange={(guidelines) => updateEvaluation({ guidelines })} />
      </Card>,
    },
  ] : [];

  return (
    <>
    <Drawer
      className="case-editor-drawer"
      title={<div className="case-editor-title"><span>{title || (value ? value.scenario || value.sample_id : "编辑用例")}</span><small>{subtitle || "结构化编辑"}</small></div>}
      width={1120}
      open={open}
      onClose={onClose}
      extra={
        variant === "criteria" ? (
          <Space>
            <Button onClick={onClose}>取消</Button>
            <Popconfirm
              title="覆盖当前 benchmark？"
              description="保存后会更新当前 benchmark 中的这条用例；当前 run 已产生的分数不会改变。"
              okText="确认覆盖"
              cancelText="取消"
              okButtonProps={{ danger: true }}
              onConfirm={onOverwrite}
              disabled={isBuiltin}
            >
              <Button danger loading={saving} disabled={loading || !value || isBuiltin}>
                覆盖当前 benchmark
              </Button>
            </Popconfirm>
          </Space>
        ) : (
          <Button icon={<CodeOutlined />} onClick={() => void openSourceYaml()} disabled={loading || !value}>查看源 YAML</Button>
        )
      }
      footer={variant === "criteria" ? null : <div className="case-editor-footer"><Popconfirm title="确认删除这条用例？删除后不可恢复。" okText="删除" cancelText="取消" onConfirm={onDelete}><Button danger disabled={source === "builtin"}>删除用例</Button></Popconfirm><Space><Button onClick={onClose}>取消</Button><Button type="primary" loading={saving} disabled={loading || !value} onClick={onSave}>保存用例</Button></Space></div>}
    >
      {loading || !value ? <Spin tip="正在加载用例内容…" /> : (
        <div className="case-editor-layout">
          {benchmarkLabel ? <Typography.Paragraph type="secondary">当前 benchmark：<Typography.Text strong>{benchmarkLabel}</Typography.Text></Typography.Paragraph> : null}
          {headerContent ? <div style={{ marginBottom: 16 }}>{headerContent}</div> : null}
          {source === "builtin" && <Typography.Text type="warning">内置用例可查看，但不建议直接修改；生产镜像重建后修改可能丢失。</Typography.Text>}
          <div className="case-editor-meta"><span>用例编号 <strong>{value.sample_id}</strong></span><span>来源文件 <strong>{caseFile || "—"}</strong></span><span>{saveHint || "保存后将同步更新源 YAML"}</span></div>
          <Tabs className="case-editor-tabs" defaultActiveKey="basic" items={tabItems} />
        </div>
      )}
    </Drawer>
    {variant === "benchmark" ? (
      <Drawer title="源 YAML（只读）" width={680} open={sourceOpen} onClose={() => setSourceOpen(false)} extra={<Button onClick={() => setSourceOpen(false)}>关闭</Button>}>
        <Typography.Paragraph type="secondary">这里展示最近一次保存后的源文件内容。当前界面的未保存修改会在点击“保存用例”后同步写回 YAML。</Typography.Paragraph>
        <Input.TextArea value={sourceYaml} readOnly placeholder={sourceLoading ? "正在加载源 YAML…" : ""} autoSize={{ minRows: 24, maxRows: 42 }} className="case-editor-source-yaml" />
      </Drawer>
    ) : null}
    </>
  );
}
