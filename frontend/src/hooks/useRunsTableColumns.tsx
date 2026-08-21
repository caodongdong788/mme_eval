import { DeleteOutlined } from "@ant-design/icons";
import { Popconfirm, Progress, Space, Tooltip } from "antd";
import type { ColumnsType } from "antd/es/table";
import type { ProgressInfo, RunSummary } from "../api";
import {
  DashTableActions,
  DashTableDangerLink,
  DashTableNavLink,
} from "../components/DashTableActions";
import { FeishuMention } from "../components/FeishuMention";
import { RunStatusTag } from "../components/RunStatusTag";
import { RunTriggerTag } from "../components/RunTriggerTag";
import { humanizeErrorText } from "../utils/apiError";
import { formatApiDateTime } from "../utils/datetime";

const nowrap = { onCell: () => ({ style: { whiteSpace: "nowrap" as const } }) };
const wrapCell = {
  onCell: () => ({
    style: { whiteSpace: "normal" as const, wordBreak: "break-word" as const },
  }),
};

export function useRunsTableColumns(
  progress: Record<number, ProgressInfo>,
  onDelete: (id: number) => Promise<void>
): ColumnsType<RunSummary> {
  return [
    { title: "ID", dataIndex: "id", width: "7%", ...nowrap, className: "runs-table__mono" },
    {
      title: "名称",
      dataIndex: "name",
      width: "18%",
      ...wrapCell,
      render: (name: string, run: RunSummary) => (
        <Space size={4} wrap>
          <DashTableNavLink to={`/runs/${run.id}`}>
            {name || run.run_slug}
          </DashTableNavLink>
          {run.pinned && <span className="runs-table__pin">置顶</span>}
        </Space>
      ),
    },
    {
      title: "任务类型",
      dataIndex: "trigger_type",
      width: "10%",
      ...nowrap,
      render: (type: RunSummary["trigger_type"]) => <RunTriggerTag type={type} />,
    },
    {
      title: "状态",
      dataIndex: "status",
      width: "11%",
      render: (status: string, run: RunSummary) => {
        if (status === "running" || status === "pending") {
          const current = progress[run.id]?.progress;
          const percent = Math.max(0, Math.min(100, Number(current?.percent) || 0));
          return (
            <div className="runs-table__running-status">
              <RunStatusTag status={status} />
              {current && (
                <Tooltip
                  title={`${current.current_label || ""} ${current.done || 0}/${current.total || 0}`}
                >
                  <div className="runs-table__progress-row">
                    <Progress
                      percent={percent}
                      showInfo={false}
                      size="small"
                      strokeColor="var(--runs-purple)"
                    />
                    <span className="runs-table__progress-text">
                      {percent.toFixed(1)}%
                    </span>
                  </div>
                </Tooltip>
              )}
            </div>
          );
        }
        if (status === "failed") {
          return (
            <Tooltip
              title={humanizeErrorText(
                run.error_msg,
                "评测执行失败，请查看详情或重新评测"
              )}
            >
              <RunStatusTag status={status} />
            </Tooltip>
          );
        }
        return <RunStatusTag status={status} />;
      },
    },
    {
      title: "通过率",
      dataIndex: "pass_rate",
      width: "11%",
      ...nowrap,
      render: (value: number, run: RunSummary) =>
        run.status === "success" ? (
          <span className="runs-table__pass">
            {(value * 100).toFixed(1)}% ({run.passed}/{run.total})
          </span>
        ) : (
          "—"
        ),
    },
    {
      title: "安全失败",
      dataIndex: "medical_safety_failed",
      width: "8%",
      ...nowrap,
      render: (value: number, run: RunSummary) =>
        run.status === "success" ? (
          value > 0 ? <span className="runs-table__danger">{value}</span> : "0"
        ) : (
          "—"
        ),
    },
    { title: "N", dataIndex: "n_runs", width: "4%", ...nowrap },
    {
      title: "创建人",
      dataIndex: "created_by",
      width: "10%",
      ...nowrap,
      className: "runs-table__creator",
      render: (name?: string | null) => <FeishuMention name={name} />,
    },
    {
      title: "创建时间",
      dataIndex: "created_at",
      width: "11%",
      ...nowrap,
      render: (value?: string) => formatApiDateTime(value),
    },
    {
      title: "操作",
      width: "11%",
      ...wrapCell,
      render: (_: unknown, run: RunSummary) => {
        const busy = run.status === "running" || run.status === "pending";
        return (
          <DashTableActions>
            <DashTableNavLink to={`/runs/${run.id}`}>看板</DashTableNavLink>
            <Popconfirm
              title="确认删除该评测？"
              description={
                busy
                  ? "将立即终止模型评测，并删除该记录、用例结果与产物，且不可恢复。"
                  : "将一并删除其用例结果与产物，且不可恢复。"
              }
              okText="删除"
              cancelText="取消"
              okButtonProps={{ danger: true }}
              onConfirm={() => void onDelete(run.id)}
            >
              <DashTableDangerLink>
                <DeleteOutlined /> 删除
              </DashTableDangerLink>
            </Popconfirm>
          </DashTableActions>
        );
      },
    },
  ];
}
