import { Modal } from "antd";

// 导出对话流水到飞书的确认弹窗（纯展示，行为由父级 onOk 注入）。
export function ExportTranscriptsModal({
  open,
  caseCount,
  loading,
  onOk,
  onCancel,
}: {
  open: boolean;
  caseCount: number;
  loading: boolean;
  onOk: () => void;
  onCancel: () => void;
}) {
  return (
    <Modal
      title="导出对话流水到飞书"
      open={open}
      onOk={onOk}
      onCancel={onCancel}
      confirmLoading={loading}
      okText="导出"
      cancelText="取消"
    >
      <p style={{ marginBottom: 0 }}>
        将按当前过滤条件导出 {caseCount} 条用例的对话流水，上传到你本人的飞书空间。
      </p>
    </Modal>
  );
}
