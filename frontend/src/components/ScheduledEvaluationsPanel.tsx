import { useEffect, useMemo, useState } from "react";
import {
  Button, Checkbox, Form, Input, InputNumber, Modal, Popconfirm, Radio,
  Select, Space, Switch, Table, Tag, TimePicker, Tooltip, message,
} from "antd";
import { CaretRightOutlined, DeleteOutlined, EditOutlined, PlusOutlined, ReloadOutlined } from "@ant-design/icons";
import dayjs from "dayjs";
import { api, type Benchmark, type JudgeModel, type ScheduledEvaluation, type ScheduledEvaluationPayload } from "../api";
import { formatApiDateTime } from "../utils/datetime";
import { formatApiError } from "../utils/apiError";
import { DashTableActions, DashTableDangerLink, DashTableLink } from "./DashTableActions";

const weekOptions = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"].map((label, value) => ({ label, value }));
function clockValue(value: string) {
  const [hour, minute] = value.split(":").map(Number);
  return dayjs().hour(hour || 0).minute(minute || 0).second(0).millisecond(0);
}

function scheduleLabel(row: ScheduledEvaluation) {
  if (row.schedule_kind === "daily") return `每天 ${row.schedule_time}`;
  return `每周 ${row.weekdays.map((day) => weekOptions[day]?.label).filter(Boolean).join("、")} ${row.schedule_time}`;
}

export function ScheduledEvaluationsPanel() {
  const [form] = Form.useForm();
  const [rows, setRows] = useState<ScheduledEvaluation[]>([]);
  const [benchmarks, setBenchmarks] = useState<Benchmark[]>([]);
  const [models, setModels] = useState<JudgeModel[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [runningTaskId, setRunningTaskId] = useState<number | null>(null);
  const [open, setOpen] = useState(false);
  const [editing, setEditing] = useState<ScheduledEvaluation | null>(null);
  const scheduleKind = Form.useWatch("schedule_kind", form) ?? "daily";
  const evaluationMode = Form.useWatch("evaluation_mode", form) ?? "single_turn";
  const judgeEnabled = Form.useWatch("enable_judge", form) ?? true;
  const autoAttributionEnabled = Form.useWatch("auto_attribution_enabled", form) ?? false;
  const selectedBenchmarkId = Form.useWatch("benchmark_id", form);
  const selectedBenchmark = useMemo(
    () => benchmarks.find((item) => item.id === selectedBenchmarkId),
    [benchmarks, selectedBenchmarkId]
  );

  const reload = async () => {
    setLoading(true);
    try {
      const [tasks, sets, judgeModels] = await Promise.all([
        api.listScheduledEvaluations(), api.listBenchmarks(), api.listJudgeModels(),
      ]);
      setRows(tasks); setBenchmarks(sets); setModels(judgeModels);
    } catch (error) {
      message.error(formatApiError(error, "加载定时任务失败"));
    } finally { setLoading(false); }
  };
  useEffect(() => { void reload(); }, []);

  const openCreate = () => {
    setEditing(null);
    form.resetFields();
    form.setFieldsValue({
      enabled: true, schedule_kind: "daily", schedule_time: clockValue("09:00"),
      evaluation_mode: "single_turn", levels: [], limit: 0, repeat: 1,
      enable_rag: false, enable_judge: true, weekdays: [],
      auto_attribution_enabled: false, auto_attribution_grades: ["不合格"], auto_attribution_model_id: null,
    });
    setOpen(true);
  };
  const openEdit = (row: ScheduledEvaluation) => {
    setEditing(row);
    form.setFieldsValue({
      ...row,
      auto_attribution_grades: ["不合格"],
      auto_attribution_model_id: row.auto_attribution_model_id ?? null,
      schedule_time: clockValue(row.schedule_time),
    });
    setOpen(true);
  };
  const save = async (values: Record<string, unknown>) => {
    const payload: ScheduledEvaluationPayload = {
      name: String(values.name || "").trim(), benchmark_id: Number(values.benchmark_id),
      enabled: Boolean(values.enabled), schedule_kind: values.schedule_kind as "daily" | "weekly",
      schedule_time: (values.schedule_time as dayjs.Dayjs).format("HH:mm"),
      weekdays: (values.schedule_kind === "weekly" ? values.weekdays : []) as number[],
      evaluation_mode: values.evaluation_mode as "single_turn" | "multi_turn",
      levels: (values.levels as string[]) || [], limit: Number(values.limit || 0), repeat: Number(values.repeat || 1),
      enable_rag: Boolean(values.enable_rag), enable_judge: Boolean(values.enable_judge),
      judge_model_id: values.enable_judge ? Number(values.judge_model_id) || null : null,
      user_simulator_model_id: values.evaluation_mode === "multi_turn" ? Number(values.user_simulator_model_id) || null : null,
      auto_attribution_enabled: Boolean(values.auto_attribution_enabled && values.enable_judge),
      auto_attribution_grades: values.auto_attribution_enabled && values.enable_judge ? ["不合格"] : [],
      auto_attribution_model_id: values.auto_attribution_enabled && values.enable_judge
        ? Number(values.auto_attribution_model_id) || null
        : null,
    };
    setSaving(true);
    try {
      if (editing) await api.updateScheduledEvaluation(editing.id, payload);
      else await api.createScheduledEvaluation(payload);
      message.success(editing ? "定时任务已更新" : "定时任务已创建");
      setOpen(false); await reload();
    } catch (error) { message.error(formatApiError(error, "保存失败")); }
    finally { setSaving(false); }
  };
  const toggle = async (row: ScheduledEvaluation, enabled: boolean) => {
    try { await api.updateScheduledEvaluation(row.id, { enabled }); setRows((items) => items.map((item) => item.id === row.id ? { ...item, enabled } : item)); }
    catch (error) { message.error(formatApiError(error, "更新状态失败")); }
  };
  const remove = async (id: number) => {
    try { await api.deleteScheduledEvaluation(id); message.success("定时任务已删除"); await reload(); }
    catch (error) { message.error(formatApiError(error, "删除失败")); }
  };
  const runNow = async (row: ScheduledEvaluation) => {
    setRunningTaskId(row.id);
    try {
      const run = await api.runScheduledEvaluationNow(row.id);
      message.success(`已发起回归任务 #${run.id}`);
      await reload();
    } catch (error) {
      message.error(formatApiError(error, "立即执行失败"));
    } finally {
      setRunningTaskId(null);
    }
  };

  const columns = [
    { title: "任务名称", dataIndex: "name", width: 220, render: (value: string) => <strong>{value}</strong> },
    { title: "Benchmark", dataIndex: "benchmark_id", render: (id: number) => benchmarks.find((item) => item.id === id)?.name || `#${id}` },
    { title: "触发频率", width: 190, render: (_: unknown, row: ScheduledEvaluation) => scheduleLabel(row) },
    { title: "状态", width: 110, render: (_: unknown, row: ScheduledEvaluation) => <Switch checked={row.enabled} checkedChildren="启用" unCheckedChildren="停用" onChange={(checked) => void toggle(row, checked)} /> },
    { title: "运行参数", width: 330, render: (_: unknown, row: ScheduledEvaluation) => <Space size={4} wrap><Tag>{row.evaluation_mode === "multi_turn" ? "多轮" : "单轮"}</Tag><Tag color={row.enable_rag ? "green" : "default"}>RAG {row.enable_rag ? "开" : "关"}</Tag><Tag>N={row.repeat}</Tag>{row.enable_judge && <Tag color="purple">判分</Tag>}{row.auto_attribution_enabled && <Tag color="gold">自动归因：不合格</Tag>}</Space> },
    { title: "下次执行", dataIndex: "next_run_at", width: 170, render: (value: string) => formatApiDateTime(value) },
    { title: "上次执行", dataIndex: "last_run_at", width: 170, render: (value: string, row: ScheduledEvaluation) => row.last_error ? <Tooltip title={row.last_error}><span className="runs-table__danger">触发失败</span></Tooltip> : formatApiDateTime(value) },
    {
      title: "操作",
      width: 160,
      render: (_: unknown, row: ScheduledEvaluation) => (
        <DashTableActions>
          <DashTableLink onClick={() => void runNow(row)} disabled={runningTaskId === row.id}>
            <CaretRightOutlined /> {runningTaskId === row.id ? "启动中" : "立即执行"}
          </DashTableLink>
          <DashTableLink onClick={() => openEdit(row)}><EditOutlined /> 编辑</DashTableLink>
          <Popconfirm title="确认删除该定时任务？" onConfirm={() => void remove(row.id)}>
            <DashTableDangerLink><DeleteOutlined /> 删除</DashTableDangerLink>
          </Popconfirm>
        </DashTableActions>
      ),
    },
  ];

  return <>
    <div className="dash-table-card">
      <div className="scheduled-evaluation-head"><div><h3>定时评测任务</h3><p>按上海时间自动创建评测 run；每次执行都会在评测记录中标记为“定时任务触发”。</p></div><Space><Button icon={<ReloadOutlined />} onClick={() => void reload()} loading={loading}>刷新</Button><Button type="primary" icon={<PlusOutlined />} onClick={openCreate}>新增定时任务</Button></Space></div>
      <Table className="dash-table" rowKey="id" loading={loading} columns={columns} dataSource={rows} scroll={{ x: 1400 }} pagination={false} />
    </div>
    <Modal open={open} title={editing ? "编辑定时评测任务" : "新增定时评测任务"} width={780} okText="保存" cancelText="取消" confirmLoading={saving} onCancel={() => setOpen(false)} onOk={() => form.submit()}>
      <Form form={form} layout="vertical" onFinish={(values) => void save(values)}>
        <Form.Item name="enabled" valuePropName="checked" hidden><Switch /></Form.Item>
        <Form.Item name="name" label="任务名称" rules={[{ required: true, message: "请输入任务名称" }]}><Input placeholder="如：每日真实患者集回归" maxLength={200} /></Form.Item>
        <Form.Item name="benchmark_id" label="Benchmark 用例集" rules={[{ required: true, message: "请选择 benchmark" }]}><Select showSearch optionFilterProp="label" options={benchmarks.map((item) => ({ value: item.id, label: `${item.name}（${item.case_count} 条）` }))} /></Form.Item>
        <Space align="start" size={24} wrap><Form.Item name="schedule_kind" label="执行频率"><Radio.Group options={[{ value: "daily", label: "每天" }, { value: "weekly", label: "每周" }]} optionType="button" /></Form.Item><Form.Item name="schedule_time" label="执行时间" rules={[{ required: true }]}><TimePicker format="HH:mm" minuteStep={5} allowClear={false} /></Form.Item></Space>
        {scheduleKind === "weekly" && <Form.Item name="weekdays" label="执行日" rules={[{ required: true, message: "至少选择一天" }]}><Checkbox.Group options={weekOptions} /></Form.Item>}
        <Form.Item name="evaluation_mode" label="对话评测模式"><Radio.Group options={[{ value: "single_turn", label: "单轮对话" }, { value: "multi_turn", label: "多轮对话" }]} optionType="button" /></Form.Item>
        {evaluationMode === "multi_turn" && <Form.Item name="user_simulator_model_id" label="语义追问模型"><Select allowClear options={models.map((item) => ({ value: item.id, label: `${item.name} · ${item.model}${item.has_api_key ? "" : "（未配 Key）"}` }))} /></Form.Item>}
        <Form.Item name="levels" label="Level 筛选（不选则全部）"><Checkbox.Group options={(selectedBenchmark?.levels || []).map((value) => ({ value, label: value }))} /></Form.Item>
        <Space size={24} wrap><Form.Item name="repeat" label="重复次数（N）"><InputNumber min={1} /></Form.Item><Form.Item name="limit" label="限制条数（0=全部）"><InputNumber min={0} /></Form.Item></Space>
        <Form.Item name="enable_rag" label="启用医学文献 RAG" valuePropName="checked"><Switch /></Form.Item>
        <Form.Item name="enable_judge" label="启用 LLM 判分" valuePropName="checked"><Switch /></Form.Item>
        <Form.Item name="judge_model_id" label="打分模型"><Select allowClear disabled={!judgeEnabled} placeholder={judgeEnabled ? "不选则使用平台默认" : "已关闭 LLM 判分"} options={models.map((item) => ({ value: item.id, label: `${item.name} · ${item.model}${item.has_api_key ? "" : "（未配 Key）"}` }))} /></Form.Item>
        <Form.Item name="auto_attribution_enabled" label="自动归因不合格 Case" valuePropName="checked" extra="仅定时评测生效。归因模型与判分模型不同时，每完成一个不合格 Case 就立即加入同一个归因任务；合格、良好、优秀自动跳过。"><Switch disabled={!judgeEnabled} /></Form.Item>
        {autoAttributionEnabled && <Form.Item name="auto_attribution_model_id" label="归因模型" rules={[{ required: true, message: "请选择归因模型" }]}><Select options={models.map((item) => ({ value: item.id, label: `${item.name} · ${item.model}${item.has_api_key ? "" : "（未配 Key）"}` }))} placeholder="选择用于归因分析的模型" /></Form.Item>}
      </Form>
    </Modal>
  </>;
}
