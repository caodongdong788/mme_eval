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
  Switch,
  Tabs,
  Tooltip,
  Typography,
} from "antd";
import { CodeOutlined, DeleteOutlined, PlusOutlined } from "@ant-design/icons";
import { type ReactNode, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { DIM_LABEL, EVALUATION_DIMENSION_ROLE, EVALUATION_DIMENSIONS, EVALUATION_ROLE_LABEL, EVALUATION_ROLE_ORDER } from "../labels";
import type { JsonObject } from "../api";
import { AGENT_TOOL_BY_NAME, AGENT_TOOL_CATALOG, type AgentToolCatalogItem } from "../agentToolCatalog";
import {
  AGENT_RETRIEVAL_SOURCE_CATALOG,
  resolveAgentRetrievalSource,
  type AgentRetrievalSourceCatalogItem,
} from "../agentRetrievalSourceCatalog";
import {
  formatProfileMemoryEntry,
  parseProfileMemoryEntry,
  PROFILE_MEMORY_CATEGORY_OPTIONS,
  type ProfileMemoryCategory,
} from "../profileMemory";
import {
  MODEL_COMPARISON_DIMENSIONS,
  MODEL_COMPARISON_DIMENSION_LABELS,
} from "../utils/scoringStandards";

type CaseData = JsonObject;
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

function updateItemAt(items: CaseData[], index: number, patch: CaseData): CaseData[] {
  return items.map((item, itemIndex) =>
    itemIndex === index ? { ...item, ...patch } : item,
  );
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
            className="case-editor-pair-key"
            aria-label="字段名称"
            value={key}
            onChange={(event) => update(index, event.target.value, entryValue)}
            placeholder="字段名称"
          />
          {variant === "profile" ? (
            <Input
              className="case-editor-pair-value"
              aria-label="字段内容"
              value={asText(entryValue)}
              onChange={(event) => update(index, key, parseText(event.target.value))}
              placeholder="字段内容"
              title={asText(entryValue)}
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

function RequirementList({
  value,
  onChange,
  placeholder = "请输入该维度的要求",
  addText = "新增要求",
}: {
  value: unknown;
  onChange: (next: string[]) => void;
  placeholder?: string;
  addText?: string;
}) {
  const items = Array.isArray(value) ? value.map(String) : value ? [String(value)] : [];
  return (
    <div className="case-editor-requirement-list">
      {items.map((item, index) => (
        <div className="case-editor-requirement" key={index}>
          <span className="case-editor-requirement__index">{index + 1}</span>
          <Input.TextArea
            value={item}
            placeholder={placeholder}
            autoSize={{ minRows: 2, maxRows: 6 }}
            onChange={(event) => onChange(items.map((v, i) => (i === index ? event.target.value : v)))}
          />
          <Button type="text" danger icon={<DeleteOutlined />} aria-label="删除要求" onClick={() => onChange(items.filter((_, i) => i !== index))} />
        </div>
      ))}
      <Button type="dashed" size="small" icon={<PlusOutlined />} onClick={() => onChange([...items, ""])}>
        {addText}
      </Button>
    </div>
  );
}

function ProfileMemoryEditor({ value, onChange }: { value: unknown; onChange: (next: string[]) => void }) {
  const entries = (Array.isArray(value) ? value : value ? [value] : []).map(parseProfileMemoryEntry);
  const update = (index: number, patch: { category?: ProfileMemoryCategory; content?: string }) => {
    onChange(entries.map((entry, entryIndex) => {
      const next = entryIndex === index ? { ...entry, ...patch } : entry;
      return formatProfileMemoryEntry(next.category, next.content);
    }));
  };
  return (
    <div className="case-editor-profile-memory-list">
      {entries.map((entry, index) => (
        <div className="case-editor-profile-memory-row" key={index}>
          <span className="case-editor-requirement__index">{index + 1}</span>
          <label className="case-editor-input-field case-editor-profile-memory-category">
            <span className="case-editor-input-field__label">画像分类</span>
            <Select
              aria-label={`画像分类 ${index + 1}`}
              classNames={{ popup: { root: "case-editor-profile-memory-dropdown" } }}
              value={entry.category}
              placeholder="请选择分类"
              options={PROFILE_MEMORY_CATEGORY_OPTIONS.map((item) => ({ ...item, label: item.value }))}
              optionRender={(option) => {
                const item = option.data as unknown as { value: ProfileMemoryCategory; description: string };
                return (
                  <Tooltip title={item.description} placement="right" mouseEnterDelay={0.2}>
                    <div className="case-editor-profile-memory-option" title={item.description}>
                      <strong>{item.value}</strong>
                      <span>{item.description}</span>
                    </div>
                  </Tooltip>
                );
              }}
              onChange={(category) => update(index, { category })}
            />
          </label>
          <label className="case-editor-input-field case-editor-profile-memory-content">
            <span className="case-editor-input-field__label">画像内容</span>
            <Input.TextArea
              aria-label={`画像内容 ${index + 1}`}
              value={entry.content}
              placeholder="请输入稳定偏好、习惯或长期背景"
              autoSize={{ minRows: 1, maxRows: 4 }}
              onChange={(event) => update(index, { content: event.target.value })}
            />
          </label>
          <Button
            type="text"
            danger
            icon={<DeleteOutlined />}
            aria-label={`删除画像记忆 ${index + 1}`}
            onClick={() => onChange(entries.filter((_, entryIndex) => entryIndex !== index).map((item) => formatProfileMemoryEntry(item.category, item.content)))}
          />
        </div>
      ))}
      <Button type="dashed" size="small" icon={<PlusOutlined />} onClick={() => onChange([...entries.map((item) => formatProfileMemoryEntry(item.category, item.content)), "[关注] "])}>
        新增画像记忆
      </Button>
    </div>
  );
}

function ResponsePreferencesEditor({ value, onChange }: { value: unknown; onChange: (next: CaseData[]) => void }) {
  const items: CaseData[] = Array.isArray(value)
    ? value.map((item) => item && typeof item === "object" && !Array.isArray(item) ? { ...item } : { preference: String(item ?? ""), basis: "" })
    : [];
  const update = (index: number, patch: CaseData) => onChange(updateItemAt(items, index, patch));
  return (
    <div className="case-editor-response-preference-list">
      {items.map((item, index) => (
        <Card
          key={`${index}-${String(item.preference || "")}`}
          size="small"
          className="case-editor-object-card case-editor-response-preference-card"
          title={<span className="case-editor-object-card__title"><em>{String(index + 1).padStart(2, "0")}</em><strong>{String(item.preference || "尚未填写偏好内容")}</strong></span>}
          extra={<Button type="text" danger icon={<DeleteOutlined />} onClick={() => onChange(items.filter((_, itemIndex) => itemIndex !== index))}>删除</Button>}
        >
          <div className="case-editor-response-preference-fields">
            <label className="case-editor-input-field">
              <span className="case-editor-input-field__label">偏好内容</span>
              <Input.TextArea
                aria-label={`偏好内容 ${index + 1}`}
                value={String(item.preference || "")}
                placeholder="例如：先给结论，再说明数据依据"
                autoSize={{ minRows: 1, maxRows: 4 }}
                onChange={(event) => update(index, { preference: event.target.value })}
              />
            </label>
            <label className="case-editor-input-field">
              <span className="case-editor-input-field__label">偏好依据（可选）</span>
              <Input.TextArea
                aria-label={`偏好依据 ${index + 1}`}
                value={String(item.basis || "")}
                placeholder="例如：用户明确表达过该偏好"
                autoSize={{ minRows: 1, maxRows: 4 }}
                onChange={(event) => update(index, { basis: event.target.value })}
              />
            </label>
          </div>
        </Card>
      ))}
      <Button type="dashed" size="small" icon={<PlusOutlined />} onClick={() => onChange([...items, { preference: "", basis: "" }])}>
        新增回复偏好
      </Button>
    </div>
  );
}

const MEDICAL_DOCUMENT_TYPE_OPTIONS = [
  { value: "outpatient", label: "门诊病历" },
  { value: "pathology", label: "病理报告" },
  { value: "imaging", label: "影像报告" },
  { value: "discharge", label: "出院记录" },
  { value: "lab", label: "检验报告" },
  { value: "other", label: "其他资料" },
];

function MedicalMetricsEditor({ value, documentDate, onChange }: { value: unknown; documentDate: string; onChange: (next: CaseData[]) => void }) {
  const metrics: CaseData[] = Array.isArray(value) ? value.map((item) => item && typeof item === "object" && !Array.isArray(item) ? { ...item } : {}) : [];
  const update = (index: number, patch: CaseData) => onChange(updateItemAt(metrics, index, patch));
  return (
    <div className="case-editor-medical-entry-list">
      {metrics.map((metric, index) => {
        const numericValue = metric.value == null || metric.value === "" || !Number.isFinite(Number(metric.value)) ? null : Number(metric.value);
        return (
          <Card className="case-editor-medical-entry-card case-editor-medical-metric-card" size="small" key={`${String(metric.name || index)}-${index}`} title={<span>指标 {String(index + 1).padStart(2, "0")} · <strong>{String(metric.name || "尚未填写名称")}</strong></span>} extra={<Button type="text" danger icon={<DeleteOutlined />} onClick={() => onChange(metrics.filter((_, itemIndex) => itemIndex !== index))}>删除</Button>}>
            <div className="case-editor-medical-field-grid case-editor-medical-metric-grid">
              <label className="case-editor-input-field"><span className="case-editor-input-field__label">指标名称</span><Input value={String(metric.name || "")} placeholder="例如 CA15-3" onChange={(event) => update(index, { name: event.target.value })} /></label>
              <label className="case-editor-input-field"><span className="case-editor-input-field__label">数值</span><InputNumber value={numericValue} placeholder="数值或右侧文字结果" onChange={(numberValue) => update(index, { value: numberValue })} /></label>
              <label className="case-editor-input-field"><span className="case-editor-input-field__label">文字结果</span><Input value={String(metric.text_value || "")} placeholder="例如 阳性、未见异常" onChange={(event) => update(index, { text_value: event.target.value })} /></label>
              <label className="case-editor-input-field"><span className="case-editor-input-field__label">单位（可选）</span><Input value={String(metric.unit || "")} placeholder="例如 U/mL" onChange={(event) => update(index, { unit: event.target.value })} /></label>
              <label className="case-editor-input-field"><span className="case-editor-input-field__label">检测日期</span><Input type="date" value={String(metric.measured_at || "")} onChange={(event) => update(index, { measured_at: event.target.value })} /></label>
              <label className="case-editor-input-field case-editor-medical-trend-switch"><span className="case-editor-input-field__label">用于前后对比</span><Switch checked={metric.is_trend_metric !== false} checkedChildren="是" unCheckedChildren="否" onChange={(is_trend_metric) => update(index, { is_trend_metric })} /></label>
            </div>
          </Card>
        );
      })}
      <Button type="dashed" size="small" icon={<PlusOutlined />} onClick={() => onChange([...metrics, { name: "", value: null, text_value: "", unit: "", is_trend_metric: true, measured_at: documentDate }])}>新增结构化指标</Button>
    </div>
  );
}

function MedicalDocumentsEditor({ value, onChange }: { value: unknown; onChange: (next: CaseData[]) => void }) {
  const documents: CaseData[] = Array.isArray(value) ? value.map((item) => item && typeof item === "object" && !Array.isArray(item) ? { ...item } : {}) : [];
  const update = (index: number, patch: CaseData) => onChange(updateItemAt(documents, index, patch));
  return (
    <div className="case-editor-medical-document-list">
      {documents.map((document, index) => (
        <Card className="case-editor-medical-document-card" size="small" key={`${String(document.ref || index)}-${index}`} title={<span className="case-editor-object-card__title"><em>{String(index + 1).padStart(2, "0")}</em><strong>{String(document.title || "尚未填写资料标题")}</strong></span>} extra={<Button type="text" danger icon={<DeleteOutlined />} onClick={() => onChange(documents.filter((_, itemIndex) => itemIndex !== index))}>删除</Button>}>
          <div className="case-editor-medical-section-title">报告基础信息</div>
          <div className="case-editor-medical-document-grid">
            <label className="case-editor-input-field"><span className="case-editor-input-field__label">文档标识（唯一）</span><Input value={String(document.ref || "")} placeholder="例如 lab_20260704" onChange={(event) => update(index, { ref: event.target.value })} /></label>
            <label className="case-editor-input-field case-editor-medical-document-title"><span className="case-editor-input-field__label">资料标题</span><Input value={String(document.title || "")} placeholder="例如 复查血液指标" onChange={(event) => update(index, { title: event.target.value })} /></label>
            <label className="case-editor-input-field"><span className="case-editor-input-field__label">报告日期</span><Input type="date" value={String(document.document_date || "")} onChange={(event) => update(index, { document_date: event.target.value })} /></label>
            <label className="case-editor-input-field"><span className="case-editor-input-field__label">资料类型</span><Select value={String(document.document_type || "other")} options={MEDICAL_DOCUMENT_TYPE_OPTIONS} onChange={(document_type) => update(index, { document_type })} /></label>
          </div>
          <div className="case-editor-medical-content-section">
            <div className="case-editor-medical-section-title"><span>结构化指标</span><em>{Array.isArray(document.metrics) ? document.metrics.length : 0} 项</em></div>
            <MedicalMetricsEditor value={document.metrics} documentDate={String(document.document_date || "")} onChange={(metrics) => update(index, { metrics })} />
          </div>
        </Card>
      ))}
      <Button type="dashed" icon={<PlusOutlined />} onClick={() => onChange([...documents, { ref: `medical_doc_${documents.length + 1}`, title: "", document_date: "", document_type: "lab", metrics: [] }])}>新增报告/病历</Button>
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

function objectItems(value: unknown): CaseData[] {
  return Array.isArray(value)
    ? value.map((item) => item && typeof item === "object" && !Array.isArray(item) ? { ...item } : {})
    : [];
}

function dateTimeInputValue(value: unknown): string {
  const match = String(value || "").match(/^(\d{4}-\d{2}-\d{2}T\d{2}:\d{2})/);
  return match?.[1] || "";
}

function dateTimeFromInput(value: string, previous: unknown): string {
  if (!value) return "";
  const timezone = String(previous || "").match(/(Z|[+-]\d{2}:\d{2})$/)?.[1] || "+08:00";
  return `${value}:00${timezone}`;
}

function StructuredRecordEditor({
  value,
  onChange,
  addText,
  keyLabel,
  valueLabel,
}: {
  value: unknown;
  onChange: (next: Record<string, unknown>) => void;
  addText: string;
  keyLabel: string;
  valueLabel: string;
}) {
  const entries = pairs(value);
  const update = (index: number, key: string, nextValue: unknown) => {
    const next: Record<string, unknown> = {};
    entries.forEach(([oldKey, oldValue], entryIndex) => {
      next[entryIndex === index ? key.trim() || "未命名" : oldKey] = entryIndex === index ? nextValue : oldValue;
    });
    onChange(next);
  };
  return (
    <div className="case-editor-record-list">
      {entries.map(([key, entryValue], index) => (
        <div className="case-editor-record-row" key={`${key}-${index}`}>
          <label className="case-editor-input-field">
            <span className="case-editor-input-field__label">{keyLabel}</span>
            <Input value={key} placeholder={keyLabel} onChange={(event) => update(index, event.target.value, entryValue)} />
          </label>
          <label className="case-editor-input-field">
            <span className="case-editor-input-field__label">{valueLabel}</span>
            <Input.TextArea value={asText(entryValue)} placeholder={valueLabel} autoSize={{ minRows: 1, maxRows: 4 }} onChange={(event) => update(index, key, parseText(event.target.value))} />
          </label>
          <Button type="text" danger icon={<DeleteOutlined />} aria-label={`删除${keyLabel} ${key}`} onClick={() => onChange(Object.fromEntries(entries.filter((_, itemIndex) => itemIndex !== index)))} />
        </div>
      ))}
      <Button type="dashed" size="small" icon={<PlusOutlined />} onClick={() => onChange({ ...Object.fromEntries(entries), "": "" })}>{addText}</Button>
    </div>
  );
}

function HistoricalConversationsEditor({ value, onChange }: { value: unknown; onChange: (next: CaseData[]) => void }) {
  const conversations = objectItems(value);
  const update = (index: number, patch: CaseData) => onChange(updateItemAt(conversations, index, patch));
  return (
    <div className="case-editor-object-list case-editor-history-list">
      {conversations.map((conversation, index) => {
        const messages = objectItems(conversation.messages);
        const updateMessages = (nextMessages: CaseData[]) => update(index, { messages: nextMessages });
        return (
          <Card
            key={`${String(conversation.ref || index)}-${index}`}
            size="small"
            className="case-editor-object-card case-editor-history-card"
            title={<span><em>{String(index + 1).padStart(2, "0")}</em><strong>{String(conversation.title || "尚未填写会话标题")}</strong></span>}
            extra={<Button type="text" danger icon={<DeleteOutlined />} onClick={() => onChange(conversations.filter((_, itemIndex) => itemIndex !== index))}>删除</Button>}
          >
            <div className="case-editor-history-meta-grid">
              <label className="case-editor-input-field"><span className="case-editor-input-field__label">会话标识（唯一）</span><Input value={String(conversation.ref || "")} placeholder="例如 history_20260704" onChange={(event) => update(index, { ref: event.target.value })} /></label>
              <label className="case-editor-input-field"><span className="case-editor-input-field__label">会话标题</span><Input value={String(conversation.title || "")} placeholder="例如 上次复查指标咨询" onChange={(event) => update(index, { title: event.target.value })} /></label>
              <label className="case-editor-input-field"><span className="case-editor-input-field__label">会话开始时间（可选）</span><Input type="datetime-local" value={dateTimeInputValue(conversation.started_at)} onChange={(event) => update(index, { started_at: dateTimeFromInput(event.target.value, conversation.started_at) })} /></label>
            </div>
            <div className="case-editor-business-section">
              <div className="case-editor-medical-section-title"><span>对话消息</span><em>{messages.length} 条</em></div>
              <div className="case-editor-history-message-list">
                {messages.map((chatMessage, messageIndex) => (
                  <div className={`case-editor-history-message case-editor-history-message--${String(chatMessage.role || "user")}`} key={messageIndex}>
                    <span className="case-editor-history-message__index">{String(messageIndex + 1).padStart(2, "0")}</span>
                    <label className="case-editor-input-field case-editor-history-message__role"><Select value={String(chatMessage.role || "user")} options={[{ value: "user", label: "用户" }, { value: "assistant", label: "Agent" }]} onChange={(role) => updateMessages(messages.map((item, itemIndex) => itemIndex === messageIndex ? { ...item, role } : item))} /></label>
                    <label className="case-editor-input-field case-editor-history-message__content"><span className="case-editor-input-field__label">消息内容</span><Input.TextArea value={String(chatMessage.content || "")} placeholder="请输入历史消息内容" autoSize={{ minRows: 2, maxRows: 7 }} onChange={(event) => updateMessages(messages.map((item, itemIndex) => itemIndex === messageIndex ? { ...item, content: event.target.value } : item))} /></label>
                    <label className="case-editor-input-field case-editor-history-message__time"><span className="case-editor-input-field__label">消息时间（可选）</span><Input type="datetime-local" value={dateTimeInputValue(chatMessage.created_at)} onChange={(event) => updateMessages(messages.map((item, itemIndex) => itemIndex === messageIndex ? { ...item, created_at: dateTimeFromInput(event.target.value, item.created_at) } : item))} /></label>
                    <Button type="text" danger icon={<DeleteOutlined />} aria-label={`删除历史消息 ${messageIndex + 1}`} disabled={messages.length <= 1} onClick={() => updateMessages(messages.filter((_, itemIndex) => itemIndex !== messageIndex))} />
                  </div>
                ))}
                <Button type="dashed" size="small" icon={<PlusOutlined />} onClick={() => updateMessages([...messages, { role: messages[messages.length - 1]?.role === "user" ? "assistant" : "user", content: "", created_at: "" }])}>新增一条消息</Button>
              </div>
            </div>
          </Card>
        );
      })}
      <Button type="dashed" icon={<PlusOutlined />} onClick={() => onChange([...conversations, { ref: `history_${conversations.length + 1}`, title: "", started_at: "", messages: [{ role: "user", content: "", created_at: "" }] }])}>新增历史对话</Button>
    </div>
  );
}

const SCHEDULE_PURPOSE_OPTIONS = [
  { value: "intervention_completion_reminder", label: "疗程完成提醒" },
  { value: "medication_reminder", label: "用药提醒" },
  { value: "review_reminder", label: "复查提醒" },
  { value: "suggestion_action_reminder", label: "建议行动提醒" },
  { value: "trend_card", label: "趋势卡片" },
  { value: "undercurrent_task", label: "后台任务提醒" },
  { value: "undercurrent_care_plan", label: "照护计划" },
  { value: "cycle_self_exam", label: "周期自检" },
  { value: "custom", label: "自定义" },
];

function ScheduledTasksEditor({ value, onChange }: { value: unknown; onChange: (next: CaseData[]) => void }) {
  const tasks = objectItems(value);
  const update = (index: number, patch: CaseData) => onChange(updateItemAt(tasks, index, patch));
  return (
    <div className="case-editor-object-list case-editor-business-list">
      {tasks.map((task, index) => (
        <Card key={`${String(task.ref || index)}-${index}`} size="small" className="case-editor-object-card case-editor-business-card case-editor-business-card--schedule" title={<span><em>{String(index + 1).padStart(2, "0")}</em><strong>{String(task.task_name || "尚未填写提醒名称")}</strong></span>} extra={<Button type="text" danger icon={<DeleteOutlined />} onClick={() => onChange(tasks.filter((_, itemIndex) => itemIndex !== index))}>删除</Button>}>
          <div className="case-editor-business-grid">
            <label className="case-editor-input-field"><span className="case-editor-input-field__label">任务标识（唯一）</span><Input value={String(task.ref || "")} placeholder="例如 review_reminder_20260901" onChange={(event) => update(index, { ref: event.target.value })} /></label>
            <label className="case-editor-input-field"><span className="case-editor-input-field__label">提醒名称</span><Input value={String(task.task_name || "")} placeholder="例如 复查提醒" onChange={(event) => update(index, { task_name: event.target.value })} /></label>
            <label className="case-editor-input-field"><span className="case-editor-input-field__label">执行时间</span><Input type="datetime-local" value={dateTimeInputValue(task.due_at)} onChange={(event) => update(index, { due_at: dateTimeFromInput(event.target.value, task.due_at) })} /></label>
            <label className="case-editor-input-field"><span className="case-editor-input-field__label">提醒用途</span><Select value={String(task.purpose || "custom")} options={SCHEDULE_PURPOSE_OPTIONS} onChange={(purpose) => update(index, { purpose })} /></label>
            <label className="case-editor-input-field"><span className="case-editor-input-field__label">时间来源</span><Select value={String(task.time_source || "user_explicit")} options={[{ value: "user_explicit", label: "用户明确指定" }, { value: "ai_inferred_default", label: "系统推断默认时间" }]} onChange={(time_source) => update(index, { time_source })} /></label>
            <label className="case-editor-input-field"><span className="case-editor-input-field__label">执行方式</span><Select value={String(task.schedule_type || "once")} options={[{ value: "once", label: "单次执行" }, { value: "cron", label: "周期执行" }]} onChange={(schedule_type) => update(index, { schedule_type })} /></label>
            {task.schedule_type === "cron" ? <label className="case-editor-input-field"><span className="case-editor-input-field__label">周期规则</span><Input value={String(task.cron_expression || "")} placeholder="例如 0 9 * * 1" onChange={(event) => update(index, { cron_expression: event.target.value })} /></label> : null}
            <label className="case-editor-input-field"><span className="case-editor-input-field__label">时区</span><Select value={String(task.timezone || "Asia/Shanghai")} options={[{ value: "Asia/Shanghai", label: "中国标准时间" }]} onChange={(timezone) => update(index, { timezone })} /></label>
            <label className="case-editor-input-field"><span className="case-editor-input-field__label">点击后打开页面（可选）</span><Input value={String(task.route || "")} placeholder="例如 /medical-records" onChange={(event) => update(index, { route: event.target.value })} /></label>
            <label className="case-editor-input-field case-editor-business-wide"><span className="case-editor-input-field__label">提醒内容</span><Input.TextArea value={String(task.message || "")} placeholder="请输入届时发送给用户的内容" autoSize={{ minRows: 2, maxRows: 5 }} onChange={(event) => update(index, { message: event.target.value })} /></label>
          </div>
        </Card>
      ))}
      <Button type="dashed" icon={<PlusOutlined />} onClick={() => onChange([...tasks, { ref: `schedule_${tasks.length + 1}`, task_name: "", due_at: "", message: "", purpose: "custom", time_source: "user_explicit", schedule_type: "once", timezone: "Asia/Shanghai", route: "" }])}>新增提醒任务</Button>
    </div>
  );
}

const CHECK_IN_FIELD_TYPE_OPTIONS = [
  { value: "text", label: "文本" },
  { value: "number", label: "数值" },
  { value: "boolean", label: "是/否" },
  { value: "choice", label: "选项" },
  { value: "date", label: "日期" },
];

function CheckInFieldsEditor({ value, onChange }: { value: unknown; onChange: (next: CaseData[]) => void }) {
  const fields = objectItems(value);
  const update = (index: number, patch: CaseData) => onChange(updateItemAt(fields, index, patch));
  return (
    <div className="case-editor-check-in-fields">
      {fields.map((field, index) => (
        <div className="case-editor-check-in-field" key={`${String(field.key || index)}-${index}`}>
          <span className="case-editor-history-message__index">{String(index + 1).padStart(2, "0")}</span>
          <label className="case-editor-input-field"><span className="case-editor-input-field__label">数据标识</span><Input value={String(field.key || "")} placeholder="例如 temperature" onChange={(event) => update(index, { key: event.target.value })} /></label>
          <label className="case-editor-input-field"><span className="case-editor-input-field__label">显示名称</span><Input value={String(field.label || "")} placeholder="例如 体温" onChange={(event) => update(index, { label: event.target.value })} /></label>
          <label className="case-editor-input-field"><span className="case-editor-input-field__label">数据类型</span><Select value={String(field.type || "text")} options={CHECK_IN_FIELD_TYPE_OPTIONS} onChange={(type) => update(index, { type })} /></label>
          <label className="case-editor-input-field"><span className="case-editor-input-field__label">单位（可选）</span><Input value={String(field.unit || "")} onChange={(event) => update(index, { unit: event.target.value })} /></label>
          {field.type === "choice" ? <label className="case-editor-input-field case-editor-check-in-options"><span className="case-editor-input-field__label">可选值（用逗号分隔）</span><Input value={Array.isArray(field.options) ? field.options.join(", ") : ""} onChange={(event) => update(index, { options: event.target.value.split(/[,，]/).map((item) => item.trim()).filter(Boolean) })} /></label> : null}
          <label className="case-editor-input-field case-editor-check-in-required"><span className="case-editor-input-field__label">是否必填</span><Switch checked={field.required === true} checkedChildren="是" unCheckedChildren="否" onChange={(required) => update(index, { required })} /></label>
          <label className="case-editor-input-field"><span className="case-editor-input-field__label">多次记录汇总方式（可选）</span><Select allowClear value={field.aggregate ? String(field.aggregate) : undefined} options={[{ value: "sum", label: "求和" }, { value: "avg", label: "平均值" }, { value: "last", label: "取最新值" }]} onChange={(aggregate) => update(index, { aggregate })} /></label>
          <Button type="text" danger icon={<DeleteOutlined />} aria-label={`删除打卡字段 ${index + 1}`} onClick={() => onChange(fields.filter((_, itemIndex) => itemIndex !== index))} />
        </div>
      ))}
      <Button type="dashed" size="small" icon={<PlusOutlined />} onClick={() => onChange([...fields, { key: "", label: "", type: "text", unit: "", required: false }])}>新增字段展示配置</Button>
    </div>
  );
}

function CheckInValuesEditor({
  value,
  fields,
  onChange,
}: {
  value: unknown;
  fields: unknown;
  onChange: (next: Record<string, unknown>) => void;
}) {
  const entries = pairs(value);
  const configuredFields = objectItems(fields).filter((field) => String(field.key || "").trim());
  const update = (index: number, key: string, nextValue: unknown) => {
    const next: Record<string, unknown> = {};
    entries.forEach(([oldKey, oldValue], entryIndex) => {
      next[entryIndex === index ? key : oldKey] = entryIndex === index ? nextValue : oldValue;
    });
    onChange(next);
  };
  const add = () => {
    const existingKeys = new Set(entries.map(([key]) => key));
    const nextField = configuredFields.find((field) => !existingKeys.has(String(field.key)));
    if (nextField) onChange({ ...Object.fromEntries(entries), [String(nextField.key)]: "" });
  };
  const renderValueInput = (field: CaseData | undefined, itemValue: unknown, onValueChange: (next: unknown) => void) => {
    const type = String(field?.type || "text");
    if (type === "number") {
      const numericValue = typeof itemValue === "number" ? itemValue : Number(itemValue);
      return <InputNumber value={Number.isFinite(numericValue) ? numericValue : null} placeholder="请输入数值" onChange={(next) => onValueChange(next ?? "")} />;
    }
    if (type === "boolean") {
      return <Select value={itemValue === true || itemValue === "true" ? "true" : "false"} options={[{ value: "true", label: "是" }, { value: "false", label: "否" }]} onChange={(next) => onValueChange(next === "true")} />;
    }
    if (type === "choice") {
      const options = Array.isArray(field?.options) ? field.options.map((option) => ({ value: String(option), label: String(option) })) : [];
      return <Select value={itemValue == null ? undefined : String(itemValue)} options={options} placeholder="请选择" onChange={onValueChange} />;
    }
    if (type === "date") {
      return <Input type="date" value={String(itemValue || "")} onChange={(event) => onValueChange(event.target.value)} />;
    }
    return <Input value={asText(itemValue)} placeholder="请输入内容" onChange={(event) => onValueChange(event.target.value)} />;
  };
  const hasAvailableField = configuredFields.some((field) => !entries.some(([key]) => key === String(field.key)));
  return (
    <div className="case-editor-record-list">
      {entries.map(([key, itemValue], index) => {
        const field = configuredFields.find((item) => String(item.key) === key);
        const usedKeys = new Set(entries.map(([entryKey]) => entryKey));
        const options = configuredFields.map((item) => ({
          value: String(item.key),
          label: String(item.label || item.key),
          disabled: String(item.key) !== key && usedKeys.has(String(item.key)),
        }));
        if (!field) options.unshift({ value: key, label: "未配置的数据项", disabled: false });
        return (
          <div className="case-editor-record-row" key={`${key}-${index}`}>
            <label className="case-editor-input-field">
              <span className="case-editor-input-field__label">数据项</span>
              <Select value={key} options={options} placeholder="请先配置字段" onChange={(nextKey) => update(index, nextKey, itemValue)} />
            </label>
            <label className="case-editor-input-field">
              <span className="case-editor-input-field__label">{field?.label ? `${String(field.label)}数值` : "数据内容"}</span>
              {renderValueInput(field, itemValue, (nextValue) => update(index, key, nextValue))}
            </label>
            <Button type="text" danger icon={<DeleteOutlined />} aria-label={`删除数据项 ${field?.label || key}`} onClick={() => onChange(Object.fromEntries(entries.filter((_, itemIndex) => itemIndex !== index)))} />
          </div>
        );
      })}
      <Button type="dashed" size="small" icon={<PlusOutlined />} disabled={!hasAvailableField} onClick={add}>{configuredFields.length ? "新增打卡数据" : "请先新增字段展示配置"}</Button>
    </div>
  );
}

function CheckInsEditor({ value, onChange }: { value: unknown; onChange: (next: CaseData[]) => void }) {
  const records = objectItems(value);
  const update = (index: number, patch: CaseData) => onChange(updateItemAt(records, index, patch));
  return (
    <div className="case-editor-object-list case-editor-business-list">
      {records.map((record, index) => (
        <Card key={`${String(record.ref || index)}-${index}`} size="small" className="case-editor-object-card case-editor-business-card case-editor-business-card--check-in" title={<span><em>{String(index + 1).padStart(2, "0")}</em><strong>{String(record.title || record.category_name || "尚未填写打卡名称")}</strong></span>} extra={<Button type="text" danger icon={<DeleteOutlined />} onClick={() => onChange(records.filter((_, itemIndex) => itemIndex !== index))}>删除</Button>}>
          <div className="case-editor-business-grid">
            <label className="case-editor-input-field"><span className="case-editor-input-field__label">记录标识（唯一）</span><Input value={String(record.ref || "")} placeholder="例如 temperature_20260820" onChange={(event) => update(index, { ref: event.target.value })} /></label>
            <label className="case-editor-input-field"><span className="case-editor-input-field__label">打卡类型标识</span><Input value={String(record.category_key || "")} placeholder="例如 temperature" onChange={(event) => update(index, { category_key: event.target.value })} /></label>
            <label className="case-editor-input-field"><span className="case-editor-input-field__label">打卡类型名称</span><Input value={String(record.category_name || "")} placeholder="例如 体温" onChange={(event) => update(index, { category_name: event.target.value })} /></label>
            <label className="case-editor-input-field"><span className="case-editor-input-field__label">打卡标题</span><Input value={String(record.title || "")} placeholder="例如 今日体温" onChange={(event) => update(index, { title: event.target.value })} /></label>
            <label className="case-editor-input-field"><span className="case-editor-input-field__label">打卡时间</span><Input type="datetime-local" value={dateTimeInputValue(record.recorded_at)} onChange={(event) => update(index, { recorded_at: dateTimeFromInput(event.target.value, record.recorded_at) })} /></label>
            <label className="case-editor-input-field"><span className="case-editor-input-field__label">标签（可选）</span><Select mode="tags" value={Array.isArray(record.tags) ? record.tags.map(String) : []} tokenSeparators={[",", "，"]} placeholder="输入后回车" onChange={(tags) => update(index, { tags })} /></label>
          </div>
          <div className="case-editor-business-section">
            <div className="case-editor-medical-section-title"><span>打卡数据</span><em>{pairs(record.values).length} 项</em></div>
            <CheckInValuesEditor value={record.values} fields={record.fields} onChange={(values) => update(index, { values })} />
          </div>
          <div className="case-editor-business-section">
            <div className="case-editor-medical-section-title"><span>字段展示配置（可选）</span><em>{Array.isArray(record.fields) ? record.fields.length : 0} 项</em></div>
            <CheckInFieldsEditor value={record.fields} onChange={(fields) => update(index, { fields })} />
          </div>
        </Card>
      ))}
      <Button type="dashed" icon={<PlusOutlined />} onClick={() => onChange([...records, { ref: `check_in_${records.length + 1}`, category_key: "", category_name: "", title: "", recorded_at: "", values: {}, fields: [], tags: [] }])}>新增打卡记录</Button>
    </div>
  );
}

const UNDERCURRENT_KIND_OPTIONS = [
  { value: "care_plan_item", label: "照护计划项" },
  { value: "monitor", label: "指标监测" },
  { value: "touch", label: "主动触达" },
  { value: "escalation", label: "风险升级" },
];
const UNDERCURRENT_STATUS_OPTIONS = [
  { value: "active", label: "进行中" },
  { value: "paused", label: "已暂停" },
  { value: "done", label: "已完成" },
  { value: "cancelled", label: "已取消" },
  { value: "review_rejected", label: "审核未通过" },
  { value: "expired", label: "已过期" },
];

function UndercurrentTasksEditor({ value, onChange }: { value: unknown; onChange: (next: CaseData[]) => void }) {
  const tasks = objectItems(value);
  const update = (index: number, patch: CaseData) => onChange(updateItemAt(tasks, index, patch));
  const optionLabel = (options: { value: string; label: string }[], value: unknown) => options.find((item) => item.value === value)?.label;
  return (
    <div className="case-editor-object-list case-editor-business-list">
      {tasks.map((task, index) => (
        <Card key={`${String(task.ref || index)}-${index}`} size="small" className="case-editor-object-card case-editor-business-card case-editor-business-card--undercurrent" title={<span><em>{String(index + 1).padStart(2, "0")}</em><strong>{optionLabel(UNDERCURRENT_KIND_OPTIONS, task.kind) || "尚未选择任务类型"}</strong></span>} extra={<Button type="text" danger icon={<DeleteOutlined />} onClick={() => onChange(tasks.filter((_, itemIndex) => itemIndex !== index))}>删除</Button>}>
          <div className="case-editor-business-grid">
            <label className="case-editor-input-field"><span className="case-editor-input-field__label">任务标识（唯一）</span><Input value={String(task.ref || "")} placeholder="例如 monitor_wbc_trend" onChange={(event) => update(index, { ref: event.target.value })} /></label>
            <label className="case-editor-input-field"><span className="case-editor-input-field__label">任务类型</span><Select value={String(task.kind || "monitor")} options={UNDERCURRENT_KIND_OPTIONS} onChange={(kind) => update(index, { kind })} /></label>
            <label className="case-editor-input-field"><span className="case-editor-input-field__label">任务状态</span><Select value={String(task.status || "active")} options={UNDERCURRENT_STATUS_OPTIONS} onChange={(status) => update(index, { status })} /></label>
            <label className="case-editor-input-field"><span className="case-editor-input-field__label">下次处理时间（可选）</span><Input type="datetime-local" value={dateTimeInputValue(task.next_due_at)} onChange={(event) => update(index, { next_due_at: dateTimeFromInput(event.target.value, task.next_due_at) })} /></label>
            <label className="case-editor-input-field"><span className="case-editor-input-field__label">优先级（可选）</span><InputNumber value={task.priority == null ? null : Number(task.priority)} placeholder="数字越大优先级越高" onChange={(priority) => update(index, { priority })} /></label>
          </div>
          <div className="case-editor-business-section">
            <div className="case-editor-medical-section-title"><span>任务参数</span><em>{pairs(task.payload).length} 项</em></div>
            <StructuredRecordEditor value={task.payload} onChange={(payload) => update(index, { payload })} addText="新增任务参数" keyLabel="参数名称" valueLabel="参数内容" />
          </div>
        </Card>
      ))}
      <Button type="dashed" icon={<PlusOutlined />} onClick={() => onChange([...tasks, { ref: `undercurrent_${tasks.length + 1}`, kind: "monitor", status: "active", next_due_at: "", payload: {}, priority: null }])}>新增暗流任务</Button>
    </div>
  );
}

const ASSERTION_TYPE_LABEL: Record<string, string> = {
  tool_call: "工具调用",
  retrieval: "数据命中",
  transcript: "回答要求",
};

const ASSERTION_TYPE_HELP: Record<string, string> = {
  tool_call: "运行验收：检查 Agent 是否实际使用指定工具；不影响八维评分",
  retrieval: "运行验收：检查工具是否返回可用数据；不影响八维评分",
  transcript: "回答要求：检查 Agent 回答是否满足要求；可选择纳入八维评分",
};

const ASSERTION_TYPE_ORDER = ["tool_call", "retrieval", "transcript"];

function AssertionsEditor({ value, onChange }: { value: unknown; onChange: (next: CaseData[]) => void }) {
  const assertions: CaseData[] = Array.isArray(value) ? value.map((item) => {
    const assertion = { ...(item || {}) } as CaseData;
    // 旧 YAML 的整段对话检查只在读取时兼容；编辑界面统一按 Agent 回答范围表达。
    if (assertion.type === "transcript" && assertion.scope === "full_conversation") {
      assertion.scope = "assistant_messages";
    }
    return assertion;
  }) : [];
  const update = (index: number, patch: CaseData) => onChange(updateItemAt(assertions, index, patch));
  const add = (type: string) => {
    const used = new Set(assertions.map((item) => String(item.id || "")));
    let sequence = assertions.length + 1;
    let id = `a${String(sequence).padStart(2, "0")}`;
    while (used.has(id)) id = `a${String(++sequence).padStart(2, "0")}`;
    const expected = type === "tool_call" || type === "retrieval"
      ? { name: "", min_count: 1 }
      : { contains: "", scope: "assistant_final", match_mode: "semantic", dimensions: [], deduction: 0 };
    onChange([...assertions, { id, type, description: "", ...expected }]);
  };
  const assertionCard = (assertion: CaseData, index: number) => {
    const type = String(assertion.type || "tool_call");
    const selectedTool = type === "tool_call" ? AGENT_TOOL_BY_NAME.get(String(assertion.name || "")) : undefined;
    const retrievalSourceName = String(assertion.name || "");
    const selectedRetrievalSource = type === "retrieval" ? resolveAgentRetrievalSource(retrievalSourceName) : undefined;
    const assertionDimensions = (Array.isArray(assertion.dimensions)
      ? assertion.dimensions
      : assertion.dimension ? [assertion.dimension] : [])
      .map(String)
      .filter(Boolean)
      .slice(0, 1);
    const modelComparisonDimensions = (Array.isArray(assertion.model_comparison_dimensions)
      ? assertion.model_comparison_dimensions
      : [])
      .map(String)
      .filter(Boolean)
      .slice(0, 1);
    const hasAgentScoreDeduction = assertionDimensions.length > 0 && Number(assertion.deduction || 0) > 0;
    const hasScoreDeduction = type === "transcript" && (hasAgentScoreDeduction || modelComparisonDimensions.length > 0);
    const setScoring = (enabled: boolean) => update(index, enabled
      ? { dimension: null, dimensions: ["professional_accuracy"], model_comparison_dimensions: [], deduction: 1, model_comparison_deduction: 0, blocking: false }
      : { dimension: null, dimensions: [], model_comparison_dimensions: [], deduction: 0, model_comparison_deduction: 0, blocking: true });
    const setAgentDimensions = (dimension?: string) => {
      const selected = dimension ? [dimension] : [];
      update(index, {
        dimension: null,
        dimensions: selected,
        deduction: selected.includes("medical_safety") ? 5 : Math.max(1, Number(assertion.deduction || 1)),
      });
    };
    const setModelComparisonDimensions = (dimension?: string) => update(index, {
      model_comparison_dimensions: dimension ? [dimension] : [],
      model_comparison_deduction: dimension ? Math.max(1, Number(assertion.model_comparison_deduction || 1)) : 0,
    });
    const safetyDimensionSelected = assertionDimensions.includes("medical_safety");
    const checkScope = String(assertion.scope || "assistant_final") === "assistant_messages"
      ? "assistant_messages"
      : "assistant_final";
    return (
      <Card
        key={`${String(assertion.id || index)}-${index}`}
        size="small"
        className={`case-editor-assertion-card case-editor-assertion-card--${type}`}
        title={<span className="case-editor-assertion-title"><em>{String(index + 1).padStart(2, "0")}</em><span><strong>{ASSERTION_TYPE_LABEL[type]}检查</strong><small>{ASSERTION_TYPE_HELP[type]}</small></span></span>}
        extra={<Button type="text" danger icon={<DeleteOutlined />} onClick={() => onChange(assertions.filter((_, itemIndex) => itemIndex !== index))}>删除</Button>}
      >
        <div className="case-editor-assertion-config">
          <label className="case-editor-input-field case-editor-assertion-description">
            <span className="case-editor-input-field__label">检查名称</span>
            <Input value={String(assertion.description || "")} placeholder="例如：必须读取结构化病例指标" onChange={(event) => update(index, { description: event.target.value })} />
          </label>
        </div>
        <div className="case-editor-assertion-expectation">
          <div className="case-editor-assertion-section-title">检查条件</div>
          {type === "tool_call" || type === "retrieval" ? (
            <div className="case-editor-assertion-grid">
              <label className="case-editor-input-field">
                <span className="case-editor-input-field__label">{type === "tool_call" ? "目标工具" : "目标数据来源"}</span>
                {type === "tool_call" ? (
                  <>
                    <Select
                      classNames={{ popup: { root: "case-editor-tool-dropdown" } }}
                      showSearch
                      allowClear
                      value={String(assertion.name || "") || undefined}
                      placeholder="请选择目标工具"
                      popupMatchSelectWidth={560}
                      listHeight={420}
                      options={AGENT_TOOL_CATALOG.map((tool) => ({ value: tool.name, label: tool.name, ...tool }))}
                      filterOption={(input, option) => {
                        const tool = option as unknown as AgentToolCatalogItem | undefined;
                        return Boolean(tool && `${tool.name} ${tool.title} ${tool.description} ${tool.category}`.toLowerCase().includes(input.trim().toLowerCase()));
                      }}
                      optionRender={(option) => {
                        const tool = option.data as unknown as AgentToolCatalogItem;
                        return <div className="case-editor-tool-option"><div><strong>{tool.name}</strong><em>{tool.category}</em></div><span>{tool.title}：{tool.description}</span></div>;
                      }}
                      onChange={(name) => update(index, { name: name || "" })}
                    />
                    {selectedTool ? <div className="case-editor-selected-tool"><strong>{selectedTool.title}</strong><span>{selectedTool.description}</span></div> : null}
                  </>
                ) : (
                  <>
                    <Select
                      classNames={{ popup: { root: "case-editor-tool-dropdown" } }}
                      showSearch
                      allowClear
                      value={selectedRetrievalSource?.name || retrievalSourceName || undefined}
                      placeholder="请选择目标数据来源"
                      popupMatchSelectWidth={620}
                      listHeight={360}
                      options={AGENT_RETRIEVAL_SOURCE_CATALOG.map((source) => ({ value: source.name, label: source.name, ...source }))}
                      filterOption={(input, option) => {
                        const source = option as unknown as AgentRetrievalSourceCatalogItem | undefined;
                        return Boolean(source && `${source.name} ${source.title} ${source.description} ${source.category}`.toLowerCase().includes(input.trim().toLowerCase()));
                      }}
                      optionRender={(option) => {
                        const source = option.data as unknown as AgentRetrievalSourceCatalogItem;
                        return <div className="case-editor-tool-option"><div><strong>{source.name}</strong><em>{source.category}</em></div><span>{source.title}：{source.description}</span></div>;
                      }}
                      onChange={(name) => update(index, { name: name || "" })}
                    />
                    {selectedRetrievalSource ? (
                      <div className="case-editor-selected-tool">
                        <strong>{selectedRetrievalSource.title}</strong>
                        <span>{selectedRetrievalSource.description}</span>
                      </div>
                    ) : null}
                  </>
                )}
              </label>
              <label className="case-editor-input-field">
                <span className="case-editor-input-field__label">{type === "tool_call" ? "最少调用次数" : "最少命中次数"}</span>
                <InputNumber min={1} value={Number(assertion.min_count || 1)} onChange={(min_count) => update(index, { min_count: min_count ?? 1 })} />
              </label>
            </div>
          ) : null}
          {type === "transcript" ? (
            <>
              <div className="case-editor-assertion-grid">
                <label className="case-editor-input-field">
                  <span className="case-editor-input-field__label">核验方式</span>
                  <Select
                    value={String(assertion.match_mode || "exact")}
                    options={[
                      { value: "semantic", label: "语义满足（推荐）" },
                      { value: "exact", label: "原文逐字包含" },
                    ]}
                    onChange={(match_mode) => update(index, { match_mode })}
                  />
                </label>
                <label className="case-editor-input-field">
                  <span className="case-editor-input-field__label">检查范围</span>
                  <Select
                    value={checkScope}
                    options={[
                      { value: "assistant_final", label: "Agent 最终回答（推荐）" },
                      { value: "assistant_messages", label: "全部 Agent 回答（多轮）" },
                    ]}
                    onChange={(scope) => update(index, { scope })}
                  />
                </label>
                <label className="case-editor-input-field">
                  <span className="case-editor-input-field__label">{String(assertion.match_mode || "exact") === "semantic" ? "回答应达到的目标" : "回答必须包含的原文"}</span>
                  <Input value={String(assertion.contains || "")} placeholder="例如：说明需要复查血常规及复查目的" onChange={(event) => update(index, { contains: event.target.value })} />
                </label>
              </div>
              <div className="case-editor-assertion-score">
                <label className="case-editor-input-field">
                  <span className="case-editor-input-field__label">评分处理</span>
                  <Select
                    value={hasScoreDeduction ? "deduct" : "verify"}
                    options={[
                      { value: "verify", label: "仅运行验收，不扣分" },
                      { value: "deduct", label: "纳入八维评分（按总分判定）" },
                    ]}
                    onChange={(value) => setScoring(value === "deduct")}
                  />
                </label>
                {hasScoreDeduction ? (
                  <>
                    <label className="case-editor-input-field">
                      <span className="case-editor-input-field__label">Agent 评测八维</span>
                      <Select allowClear value={assertionDimensions[0]} options={EVALUATION_DIMENSIONS.map((dimension) => ({ value: dimension, label: DIM_LABEL[dimension] }))} onChange={setAgentDimensions} />
                    </label>
                    <label className="case-editor-input-field">
                      <span className="case-editor-input-field__label">模型对比八维</span>
                      <Select allowClear value={modelComparisonDimensions[0]} options={MODEL_COMPARISON_DIMENSIONS.map((dimension) => ({ value: dimension, label: MODEL_COMPARISON_DIMENSION_LABELS[dimension] }))} onChange={setModelComparisonDimensions} />
                    </label>
                    <label className="case-editor-input-field">
                      <span className="case-editor-input-field__label">Agent 未满足时扣分</span>
                      <InputNumber min={1} max={5} value={assertionDimensions.length ? (safetyDimensionSelected ? 5 : Number(assertion.deduction || 1)) : 0} disabled={!assertionDimensions.length || safetyDimensionSelected} onChange={(deduction) => update(index, { deduction: deduction ?? 1 })} />
                    </label>
                    <label className="case-editor-input-field">
                      <span className="case-editor-input-field__label">模型对比未满足时扣分</span>
                      <InputNumber min={1} max={5} value={modelComparisonDimensions.length ? Number(assertion.model_comparison_deduction || 1) : 0} disabled={!modelComparisonDimensions.length} onChange={(deduction) => update(index, { model_comparison_deduction: deduction ?? 1 })} />
                    </label>
                  </>
                ) : null}
              </div>
              {hasScoreDeduction && safetyDimensionSelected ? <div className="case-editor-assertion-safety-note">医学安全性回答要求未满足时，该维度直接记 0 分，整题总分归零；安全门禁不可与其他维度合并。</div> : null}
              {hasScoreDeduction && modelComparisonDimensions.length ? <div className="case-editor-assertion-score-note">以“模型对比八维”发起评测时，未满足该要求会从所选维度扣分，并计入本次评测的 40 分总分；Pairwise 仅比较已完成的评测结果。</div> : null}
            </>
          ) : null}
        </div>
      </Card>
    );
  };
  return (
    <div className="case-editor-assertion-list">
      <Tabs
        className="case-editor-assertion-tabs"
        items={ASSERTION_TYPE_ORDER.map((type) => {
          const entries = assertions.map((assertion, index) => ({ assertion, index })).filter(({ assertion }) => assertion.type === type);
          return {
            key: type,
            label: <span>{ASSERTION_TYPE_LABEL[type]} <em>{entries.length}</em></span>,
            children: (
              <div className="case-editor-assertion-module">
                <div className="case-editor-assertion-module__heading"><span>{ASSERTION_TYPE_HELP[type]}</span><Button type="primary" ghost size="small" icon={<PlusOutlined />} onClick={() => add(type)}>新增{ASSERTION_TYPE_LABEL[type]}检查</Button></div>
                {entries.length ? entries.map(({ assertion, index }) => assertionCard(assertion, index)) : <div className="case-editor-assertion-empty">暂未配置{ASSERTION_TYPE_LABEL[type]}检查</div>}
              </div>
            ),
          };
        })}
      />
    </div>
  );
}

function GuidelinesEditor({ value, onChange }: { value: unknown; onChange: (next: CaseData[]) => void }) {
  const guidelines: CaseData[] = Array.isArray(value) ? value.map((item) => ({ ...(item || {}) })) : [];
  const update = (index: number, patch: CaseData) => onChange(updateItemAt(guidelines, index, patch));
  const createGuideline = (dimension = "professional_accuracy") => {
    const usedIds = new Set(guidelines.map((guide) => String(guide.id || "")));
    let sequence = guidelines.length + 1;
    let id = `g${String(sequence).padStart(2, "0")}`;
    while (usedIds.has(id)) {
      sequence += 1;
      id = `g${String(sequence).padStart(2, "0")}`;
    }
    return {
      id,
      dimension,
      criteria: [""],
      reference_answers: [""],
      deduction_rule: "",
      max_score: 1,
    };
  };
  const addGuideline = (dimension?: string) => onChange([...guidelines, createGuideline(dimension)]);
  const entries = guidelines.map((guide, sourceIndex) => ({ guide, sourceIndex }));
  const entriesForDimension = (dimension: string) => entries.filter(({ guide }) => guide.dimension === dimension);
  const orderedEntries = [
    ...EVALUATION_DIMENSIONS.flatMap(entriesForDimension),
    ...entries.filter(({ guide }) => !EVALUATION_DIMENSIONS.includes(guide.dimension)),
  ];
  const displayIndex = new Map(orderedEntries.map(({ sourceIndex }, index) => [sourceIndex, index + 1]));
  const roleGroups = EVALUATION_ROLE_ORDER.map((role) => ({
    role,
    dimensions: EVALUATION_DIMENSIONS.map((dimension, dimensionIndex) => ({
      dimension,
      dimensionIndex,
      entries: EVALUATION_DIMENSION_ROLE[dimension] === role ? entriesForDimension(dimension) : [],
    })).filter((group) => group.entries.length > 0),
  })).filter((group) => group.dimensions.length > 0);
  const unassignedEntries = entries.filter(({ guide }) => !EVALUATION_DIMENSIONS.includes(guide.dimension));
  const countCriteria = (guide: CaseData) => {
    const criteria = guide.criteria ?? guide.criterion;
    return Array.isArray(criteria) ? criteria.length : criteria ? 1 : 0;
  };
  const guidelineCard = (guide: CaseData, sourceIndex: number) => {
    const criteriaValue = guide.criteria ?? guide.criterion;
    const criteria = Array.isArray(criteriaValue) ? criteriaValue.map(String) : criteriaValue ? [String(criteriaValue)] : [];
    const referenceAnswers = Array.isArray(guide.reference_answers) ? guide.reference_answers.map(String) : guide.reference_answers ? [String(guide.reference_answers)] : [];
    return (
      <Card
        key={guide.id || sourceIndex}
        size="small"
        className="case-editor-guideline-card"
        title={<span className="case-editor-guideline-card__title"><em>扣分项 {String(displayIndex.get(sourceIndex) || sourceIndex + 1).padStart(2, "0")}</em><strong>{DIM_LABEL[guide.dimension as keyof typeof DIM_LABEL] || "请选择关联维度"}</strong></span>}
        extra={<Button type="text" danger icon={<DeleteOutlined />} onClick={() => onChange(guidelines.filter((_, i) => i !== sourceIndex))}>删除</Button>}
      >
        <div className="case-editor-guide-meta">
          <label className="case-editor-input-field"><span>关联评测维度</span><Select value={guide.dimension || undefined} placeholder="请选择" options={EVALUATION_DIMENSIONS.map((dimension) => ({ value: dimension, label: DIM_LABEL[dimension] }))} onChange={(dimension) => update(sourceIndex, { dimension })} /></label>
          <label className="case-editor-input-field"><span>最高扣分</span><InputNumber min={0} value={guide.max_score ?? 1} onChange={(max_score) => update(sourceIndex, { max_score: max_score ?? 0 })} /></label>
        </div>
        <Typography.Text className="case-editor-field-label">检查点</Typography.Text>
        <RequirementList value={criteria} onChange={(next) => update(sourceIndex, { criteria: next })} placeholder="请输入检查点" addText="新增检查点" />
        <Typography.Text className="case-editor-field-label">好答案（可选）</Typography.Text>
        <Typography.Paragraph className="case-editor-section-hint">用于说明理想回答的内容方向，评测时仅作质量参考，不要求逐字一致。</Typography.Paragraph>
        <RequirementList value={referenceAnswers} onChange={(next) => update(sourceIndex, { reference_answers: next })} placeholder="请输入好答案" addText="新增好答案" />
        <label className="case-editor-input-field case-editor-deduction-rule"><span>扣分规则（可选）</span><Input.TextArea value={guide.deduction_rule || ""} placeholder="例如：遗漏一项关键要求扣 1 分" autoSize={{ minRows: 2, maxRows: 5 }} onChange={(event) => update(sourceIndex, { deduction_rule: event.target.value })} /></label>
      </Card>
    );
  };
  return (
    <div className="case-editor-guideline-list">
      {roleGroups.map(({ role, dimensions }) => (
        <section className="case-editor-guideline-role-group" key={role}>
          <header className="case-editor-guideline-role-group__header"><strong>{EVALUATION_ROLE_LABEL[role]}</strong><span>{dimensions.reduce((total, group) => total + group.entries.length, 0)} 个扣分项</span></header>
          {dimensions.map(({ dimension, dimensionIndex, entries: dimensionEntries }) => (
            <section className="case-editor-guideline-dimension-group" key={dimension}>
              <header className="case-editor-guideline-dimension-group__header">
                <em>{String(dimensionIndex + 1).padStart(2, "0")}</em>
                <strong>{DIM_LABEL[dimension]}</strong>
                <div className="case-editor-guideline-dimension-group__actions">
                  <Button type="link" size="small" icon={<PlusOutlined />} onClick={() => addGuideline(dimension)}>新增扣分项</Button>
                  <span>{dimensionEntries.length} 个扣分项 · {dimensionEntries.reduce((total, { guide }) => total + countCriteria(guide), 0)} 个检查点</span>
                </div>
              </header>
              <div className="case-editor-guideline-dimension-group__items">{dimensionEntries.map(({ guide, sourceIndex }) => guidelineCard(guide, sourceIndex))}</div>
            </section>
          ))}
        </section>
      ))}
      {unassignedEntries.length > 0 ? (
        <section className="case-editor-guideline-role-group case-editor-guideline-role-group--unassigned">
          <header className="case-editor-guideline-role-group__header"><strong>未关联维度</strong><span>{unassignedEntries.length} 个扣分项</span></header>
          <div className="case-editor-guideline-dimension-group__items">{unassignedEntries.map(({ guide, sourceIndex }) => guidelineCard(guide, sourceIndex))}</div>
        </section>
      ) : null}
      <Button
        type="dashed"
        icon={<PlusOutlined />}
        onClick={() => addGuideline()}
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
  const dimensionDetails = (dimension: string): CaseData => {
    const item = criteria[dimension];
    return Array.isArray(item) ? { criteria: item, reference_answers: [] } : (item || {}) as CaseData;
  };
  const updateDimension = (dimension: string, patch: CaseData) => {
    const current = dimensionDetails(dimension);
    const nextDetails = { ...current, ...patch };
    const requirements = Array.isArray(nextDetails.criteria) ? nextDetails.criteria : [];
    const references = Array.isArray(nextDetails.reference_answers) ? nextDetails.reference_answers : [];
    if (requirements.length === 0 && references.length === 0) {
      const nextCriteria = { ...criteria };
      delete nextCriteria[dimension];
      updateEvaluation({ dimension_criteria: nextCriteria });
      return;
    }
    updateEvaluation({ dimension_criteria: { ...criteria, [dimension]: nextDetails } });
  };
  const clearDimension = (dimension: string) => {
    const nextCriteria = { ...criteria };
    delete nextCriteria[dimension];
    updateEvaluation({ dimension_criteria: nextCriteria });
  };
  const updateInitialState = (patch: CaseData) => update({ initial_state: { ...initialState, ...patch } });
  const updateOptionalInitialState = (key: string, nextValue: unknown) => {
    const nextState = { ...initialState };
    if (nextValue == null || (Array.isArray(nextValue) && nextValue.length === 0)) delete nextState[key];
    else nextState[key] = nextValue;
    update({ initial_state: nextState });
  };
  const updateEvaluation = (patch: CaseData) => update({ evaluation: { ...evaluation, ...patch } });
  const timelineValue = initialState.Timeline ?? initialState.timeline;
  const timelineCount = Array.isArray(timelineValue) ? timelineValue.length : 0;
  const toolState = (initialState.tool_state || {}) as CaseData;
  const listCount = (items: unknown) => Array.isArray(items) ? items.length : 0;
  const toolStateCount = listCount(toolState.scheduled_tasks) + listCount(toolState.check_ins) + listCount(toolState.undercurrent_tasks);
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
      label: "账号初始化数据",
      children: <Tabs
        className="case-editor-assertion-tabs case-editor-context-tabs"
        items={[
          {
            key: "user_profile",
            label: <span>用户档案 <em>{pairs(initialState.user_profile).length}</em></span>,
            children: <div className="case-editor-assertion-module">
              <div className="case-editor-assertion-module__heading"><span>随本次用例注入 Agent，用来检查回答是否真正结合了患者情况。</span></div>
              <Card className="case-editor-card case-editor-profile-card" title="用户档案" size="small">
                <KeyValueEditor value={(initialState.user_profile || {}) as Record<string, unknown>} onChange={(user_profile) => updateInitialState({ user_profile })} addText="添加用户档案字段" variant="profile" />
              </Card>
            </div>,
          },
          {
            key: "timeline",
            label: <span>过往事实 <em>{timelineCount}</em></span>,
            children: <div className="case-editor-assertion-module">
              <div className="case-editor-assertion-module__heading"><span>模拟 Agent 可读取的历史健康信息，每条事实的字段结构不受限制。</span></div>
              <Card className="case-editor-card case-editor-timeline-section" title="过往事实" extra={<Typography.Text type="secondary">按事实拆分，支持任意字段</Typography.Text>} size="small">
                <TimelineEditor value={timelineValue} onChange={(Timeline) => updateInitialState({ Timeline })} />
              </Card>
            </div>,
          },
          {
            key: "profile_memory",
            label: <span>长期画像 <em>{listCount(initialState.profile_memory)}</em></span>,
            children: <div className="case-editor-assertion-module">
              <div className="case-editor-assertion-module__heading"><span>Case 执行前写入 cx-agent 的 USER.md，适合初始化稳定偏好、习惯和长期背景。</span></div>
              <Card className="case-editor-card" title="长期画像记忆（USER.md）" size="small">
                <ProfileMemoryEditor value={initialState.profile_memory} onChange={(profileMemory) => updateOptionalInitialState("profile_memory", profileMemory)} />
              </Card>
            </div>,
          },
          {
            key: "response_preferences",
            label: <span>回复偏好 <em>{listCount(initialState.response_preferences)}</em></span>,
            children: <div className="case-editor-assertion-module">
              <div className="case-editor-assertion-module__heading"><span>验证 Agent 是否按账号已有的表达偏好组织回答。</span></div>
              <Card className="case-editor-card" title="回复偏好" size="small">
                <ResponsePreferencesEditor value={initialState.response_preferences} onChange={(items) => updateOptionalInitialState("response_preferences", items)} />
              </Card>
            </div>,
          },
          {
            key: "medical_documents",
            label: <span>病例夹 <em>{listCount(initialState.medical_documents)}</em></span>,
            children: <div className="case-editor-assertion-module">
              <div className="case-editor-assertion-module__heading"><span>病例资料与结构化指标会在 Case 执行前真实写入被测账号的病例夹。</span></div>
              <Card className="case-editor-card" title="病例夹与结构化指标" size="small">
                <MedicalDocumentsEditor value={initialState.medical_documents} onChange={(items) => updateOptionalInitialState("medical_documents", items)} />
              </Card>
            </div>,
          },
          {
            key: "chat_history",
            label: <span>历史对话 <em>{listCount(initialState.chat_history)}</em></span>,
            children: <div className="case-editor-assertion-module">
              <div className="case-editor-assertion-module__heading"><span>在当前评测会话开始前写入历史会话，供 search_chat_history 等链路读取。</span></div>
              <Card className="case-editor-card" title="历史对话" size="small">
                <HistoricalConversationsEditor value={initialState.chat_history} onChange={(items) => updateOptionalInitialState("chat_history", items)} />
              </Card>
            </div>,
          },
          {
            key: "tool_state",
            label: <span>工具业务数据 <em>{toolStateCount}</em></span>,
            children: <div className="case-editor-assertion-module">
              <div className="case-editor-assertion-module__heading"><span>真实写入提醒、打卡和暗流任务等业务数据，不是模拟工具返回值。</span></div>
              <Card className="case-editor-card" title="工具业务数据" size="small">
                <Tabs
                  className="case-editor-module-tabs"
                  items={[
                    {
                      key: "scheduled_tasks",
                      label: `提醒任务（${listCount(toolState.scheduled_tasks)}）`,
                      children: <ScheduledTasksEditor value={toolState.scheduled_tasks} onChange={(scheduled_tasks) => updateOptionalInitialState("tool_state", { ...toolState, scheduled_tasks })} />,
                    },
                    {
                      key: "check_ins",
                      label: `打卡记录（${listCount(toolState.check_ins)}）`,
                      children: <CheckInsEditor value={toolState.check_ins} onChange={(check_ins) => updateOptionalInitialState("tool_state", { ...toolState, check_ins })} />,
                    },
                    {
                      key: "undercurrent_tasks",
                      label: `暗流任务（${listCount(toolState.undercurrent_tasks)}）`,
                      children: <UndercurrentTasksEditor value={toolState.undercurrent_tasks} onChange={(undercurrent_tasks) => updateOptionalInitialState("tool_state", { ...toolState, undercurrent_tasks })} />,
                    },
                  ]}
                />
              </Card>
            </div>,
          },
        ]}
      />,
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
        <Collapse className="case-editor-dimension-collapse" items={EVALUATION_DIMENSIONS.map((dimension, index) => {
          const details = dimensionDetails(dimension);
          const requirementCount = Array.isArray(details.criteria) ? details.criteria.length : 0;
          const referenceCount = Array.isArray(details.reference_answers) ? details.reference_answers.length : 0;
          return {
            key: dimension,
            label: <span className="case-editor-dimension-title"><em>{String(index + 1).padStart(2, "0")}</em><span><strong>{DIM_LABEL[dimension]}</strong><small>{requirementCount ? `${requirementCount} 条要求` : "尚未配置要求"}{referenceCount ? ` · ${referenceCount} 条好答案` : ""}</small></span></span>,
            children: <div className="case-editor-dimension-content"><div className="case-editor-field-heading"><Typography.Text className="case-editor-field-label">评测要求</Typography.Text>{Object.prototype.hasOwnProperty.call(criteria, dimension) ? <Popconfirm title={`清空${DIM_LABEL[dimension]}的补充评测要求和好答案？`} okText="确认清空" cancelText="取消" onConfirm={() => clearDimension(dimension)}><Button type="link" danger size="small">清空该维度</Button></Popconfirm> : null}</div><RequirementList value={details.criteria} onChange={(requirements) => updateDimension(dimension, { criteria: requirements })} placeholder="请输入该维度的要求" addText="新增评测要求" /><Typography.Text className="case-editor-field-label">好答案（可选）</Typography.Text><Typography.Paragraph className="case-editor-section-hint">作为理想回答参考，评测时不会要求 bot 逐字复述。</Typography.Paragraph><RequirementList value={details.reference_answers} onChange={(reference_answers) => updateDimension(dimension, { reference_answers })} placeholder="请输入好答案" addText="新增好答案" /></div>,
          };
        })} />
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
    {
      key: "assertions",
      label: `运行断言（${Array.isArray(evaluation.assertions) ? evaluation.assertions.filter((item: unknown) => item && typeof item === "object" && ASSERTION_TYPE_ORDER.includes(String((item as CaseData).type || "tool_call"))).length : 0}）`,
      children: <Card className="case-editor-card case-editor-assertion-section" bordered={false}>
        <AssertionsEditor value={evaluation.assertions} onChange={(assertions) => updateEvaluation({ assertions })} />
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
