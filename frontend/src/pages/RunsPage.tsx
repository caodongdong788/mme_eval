import { useCallback, useEffect, useState } from "react";
import {
  Button,
  Card,
  Popconfirm,
  Progress,
  Space,
  Table,
  Tag,
  Tooltip,
  message,
} from "antd";
import { DeleteOutlined, ReloadOutlined, RocketOutlined } from "@ant-design/icons";
import { Link, useNavigate } from "react-router-dom";
import { api, ProgressInfo, RunSummary } from "../api";
import { formatApiError } from "../utils/apiError";
import { RunStatusTag } from "../components/RunStatusTag";

export default function RunsPage() {
  const [runs, setRuns] = useState<RunSummary[]>([]);
  const [loading, setLoading] = useState(false);
  const [progress, setProgress] = useState<Record<number, ProgressInfo>>({});
  const navigate = useNavigate();

  // 返回是否仍有进行中的任务，供轮询调度决定是否继续。
  const reload = useCallback(async (): Promise<boolean> => {
    const list = await api.listRuns();
    setRuns(list);
    const active = list.filter(
      (r) => r.status === "running" || r.status === "pending"
    );
    const entries = await Promise.all(
      active.map(async (r) => [r.id, await api.getProgress(r.id)] as const)
    );
    setProgress(Object.fromEntries(entries));
    return active.length > 0;
  }, []);

  // 仅当存在进行中任务且页面可见时才轮询；切走后台暂停，回到前台立即刷新。
  useEffect(() => {
    let stopped = false;
    let timer: number | null = null;
    const clear = () => {
      if (timer !== null) {
        window.clearInterval(timer);
        timer = null;
      }
    };
    const schedule = (hasActive: boolean) => {
      clear();
      if (!hasActive || document.visibilityState !== "visible") return;
      timer = window.setInterval(async () => {
        if (document.visibilityState !== "visible") return;
        const stillActive = await reload();
        if (!stillActive) clear();
      }, 3000);
    };
    setLoading(true);
    reload()
      .then((hasActive) => {
        if (!stopped) schedule(hasActive);
      })
      .finally(() => setLoading(false));
    const onVisibility = async () => {
      if (document.visibilityState === "visible") {
        const hasActive = await reload();
        if (!stopped) schedule(hasActive);
      } else {
        clear();
      }
    };
    document.addEventListener("visibilitychange", onVisibility);
    return () => {
      stopped = true;
      clear();
      document.removeEventListener("visibilitychange", onVisibility);
    };
  }, [reload]);

  const onDelete = async (id: number) => {
    try {
      await api.deleteRun(id);
      message.success("已删除");
      reload();
    } catch (e: any) {
      message.error(formatApiError(e, "删除失败"));
    }
  };

  // 列宽不再固定，由内容自适应（仅靠 nowrap 防止文本换行导致拥挤）。
  const nowrap = { onCell: () => ({ style: { whiteSpace: "nowrap" as const } }) };

  const columns = [
    { title: "ID", dataIndex: "id", ...nowrap },
    {
      title: "名称",
      dataIndex: "name",
      ...nowrap,
      render: (name: string, r: RunSummary) => <Link to={`/runs/${r.id}`}>{name || r.run_slug}</Link>,
    },
    {
      title: "状态",
      dataIndex: "status",
      render: (s: string, r: RunSummary) => {
        if (s === "running" || s === "pending") {
          const p = progress[r.id]?.progress;
          return (
            <Space direction="vertical" size={2} style={{ minWidth: 140 }}>
              <RunStatusTag status={s} />
              {p && (
                <Tooltip title={`${p.current_label || ""} ${p.done || 0}/${p.total || 0}`}>
                  <Progress percent={p.percent || 0} size="small" />
                </Tooltip>
              )}
            </Space>
          );
        }
        if (s === "failed") {
          return (
            <Tooltip title={r.error_msg}>
              <RunStatusTag status={s} />
            </Tooltip>
          );
        }
        return <RunStatusTag status={s} />;
      },
    },
    {
      title: "通过率",
      dataIndex: "pass_rate",
      ...nowrap,
      render: (v: number, r: RunSummary) =>
        r.status === "success" ? `${(v * 100).toFixed(1)}% (${r.passed}/${r.total})` : "-",
    },
    {
      title: "硬门槛失败",
      dataIndex: "hard_gate_failed",
      ...nowrap,
      render: (v: number, r: RunSummary) =>
        r.status === "success" ? (v > 0 ? <Tag color="red">{v}</Tag> : "0") : "-",
    },
    { title: "N", dataIndex: "n_runs", ...nowrap },
    {
      title: "创建时间",
      dataIndex: "created_at",
      ...nowrap,
      render: (v?: string) => (v ? new Date(v).toLocaleString() : "-"),
    },
    {
      title: "操作",
      ...nowrap,
      render: (_: any, r: RunSummary) => {
        const busy = r.status === "running" || r.status === "pending";
        return (
          <Space>
            <Link to={`/runs/${r.id}`}>看板</Link>
            <Popconfirm
              title="确认删除该评测？"
              description="将一并删除其用例结果与产物，且不可恢复。"
              okText="删除"
              cancelText="取消"
              okButtonProps={{ danger: true }}
              onConfirm={() => onDelete(r.id)}
              disabled={busy}
            >
              <Button
                type="link"
                danger
                size="small"
                icon={<DeleteOutlined />}
                disabled={busy}
                style={{ padding: 0 }}
              >
                删除
              </Button>
            </Popconfirm>
          </Space>
        );
      },
    },
  ];

  return (
    <Card
      title="评测列表"
      extra={
        <Space>
          <Button icon={<ReloadOutlined />} onClick={reload}>
            刷新
          </Button>
          <Button type="primary" icon={<RocketOutlined />} onClick={() => navigate("/launch")}>
            发起评测
          </Button>
        </Space>
      }
    >
      <Table rowKey="id" loading={loading} columns={columns} dataSource={runs} />
    </Card>
  );
}
