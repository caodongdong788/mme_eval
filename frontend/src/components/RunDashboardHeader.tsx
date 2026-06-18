import { Button, Input, Space, Tooltip } from "antd";
import {
  LoadingOutlined,
  PushpinOutlined,
  PushpinFilled,
  RedoOutlined,
  ReloadOutlined,
} from "@ant-design/icons";
import { RunDetail } from "../api/index";
import { RunStatusTag } from "./RunStatusTag";

export interface RunDashboardHeaderProps {
  run: RunDetail;
  editingName: boolean;
  nameDraft: string;
  savingName: boolean;
  acting: boolean;
  onNameDraftChange: (value: string) => void;
  onStartEditName: () => void;
  onCommitName: () => void;
  onRejudge: () => void;
  onResume: () => void;
  onTogglePin: () => void;
}

export function RunDashboardHeader({
  run,
  editingName,
  nameDraft,
  savingName,
  acting,
  onNameDraftChange,
  onStartEditName,
  onCommitName,
  onRejudge,
  onResume,
  onTogglePin,
}: RunDashboardHeaderProps) {
  return (
    <div className="run-head">
      <div>
        <div className="run-title">
          {editingName ? (
            <Input
              size="large"
              autoFocus
              value={nameDraft}
              onChange={(e) => onNameDraftChange(e.target.value)}
              onPressEnter={onCommitName}
              onBlur={onCommitName}
              style={{ maxWidth: 420, fontWeight: 700 }}
            />
          ) : (
            <Tooltip title="双击修改评测名称">
              <span onDoubleClick={onStartEditName} style={{ cursor: "text" }}>
                {run.name || run.run_slug}
                {savingName && <LoadingOutlined style={{ fontSize: 14, marginLeft: 8 }} />}
              </span>
            </Tooltip>
          )}
          <RunStatusTag status={run.status} bordered={false} />
        </div>
        <div className="run-meta">
          <span className="chip">judge {run.judge_overrides?.model || "config 默认"}</span>
          <span className="chip">N={run.n_runs}</span>
        </div>
      </div>
      <Space>
        <Button
          icon={<ReloadOutlined />}
          loading={acting}
          disabled={run.status !== "success"}
          title="可调判分口径/judge 模型后，对冻结留痕仅重跑判分（不调用 bot）"
          onClick={onRejudge}
        >
          重判
        </Button>
        <Button
          icon={<RedoOutlined />}
          loading={acting}
          disabled={run.status === "running" || run.status === "pending"}
          title="复用成功留痕，仅对失败/缺失用例重跑"
          onClick={onResume}
        >
          续跑
        </Button>
        <Button
          icon={run.pinned ? <PushpinFilled /> : <PushpinOutlined />}
          type={run.pinned ? "primary" : "default"}
          loading={acting}
          title="置顶保护：免于存储治理清理"
          onClick={onTogglePin}
        >
          {run.pinned ? "已置顶" : "置顶"}
        </Button>
      </Space>
    </div>
  );
}
