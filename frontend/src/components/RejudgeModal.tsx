import { Alert, Checkbox, Form, Modal, Select, Typography, type FormInstance } from "antd";
import { Benchmark, JudgeModel, selectableBenchmarks } from "../api/index";

// 离线重判弹窗：可换判据 benchmark / judge 模型 / 仅重判上线失败用例。
// 纯展示 + 表单收集；提交行为由父级 onOk 读取 form 值后注入。
export function RejudgeModal({
  open,
  loading,
  form,
  benchmarks,
  judgeModels,
  onOk,
  onCancel,
}: {
  open: boolean;
  loading: boolean;
  form: FormInstance;
  benchmarks: Benchmark[];
  judgeModels: JudgeModel[];
  onOk: () => void;
  onCancel: () => void;
}) {
  return (
    <Modal
      title="重判（可换 judge 模型）"
      open={open}
      onOk={onOk}
      onCancel={onCancel}
      confirmLoading={loading}
      okText="发起重判"
      cancelText="取消"
      width={560}
    >
      <Alert
        type="info"
        showIcon
        style={{ marginBottom: 12 }}
        message="bot 回答保持冻结，仅重跑判分。改动只作用于本次重判，不修改服务器 config.yaml。全部留空=按源 run 原配置重判。"
      />
      <Form form={form} layout="vertical" size="small">
        <Form.Item
          name="cases_benchmark_id"
          label="用哪个 benchmark 的判据重判（默认=沿用源 run 原判据）"
          style={{ marginBottom: 12 }}
        >
          <Select
            allowClear
            showSearch
            optionFilterProp="label"
            placeholder="选一个 benchmark（按 sample_id 替换冻结用例判据）"
            options={selectableBenchmarks(benchmarks).map((b) => ({
              value: b.id,
              label: `#${b.id} ${b.name}${b.created_by ? `（${b.created_by}）` : ""}`,
            }))}
          />
        </Form.Item>
        <Form.Item
          name="judge_model_id"
          label="更换 judge 模型（从判分模型库选；留空=沿用源 run 模型）"
          style={{ marginBottom: 12 }}
        >
          <Select
            allowClear
            showSearch
            optionFilterProp="label"
            placeholder="从「判分模型」库选一个已保存配置（连接信息与 Key 由服务端注入）"
            options={judgeModels.map((m) => ({
              value: m.id,
              label: `#${m.id} ${m.name}（${m.provider}/${m.model}）`,
            }))}
            notFoundContent="暂无判分模型，请先到「判分模型」页新建"
          />
        </Form.Item>
        <Form.Item name="only_release_failed" valuePropName="checked" style={{ marginBottom: 0 }}>
          <Checkbox>
            只重判上线判定失败（release_passed=false）的用例
            <Typography.Text type="secondary" style={{ fontSize: 12, display: "block" }}>
              通过用例沿用源 run 结果，仅对失败用例重跑判分，合并后重算整体分数/通过率（产出新评测）。
            </Typography.Text>
          </Checkbox>
        </Form.Item>
      </Form>
    </Modal>
  );
}
