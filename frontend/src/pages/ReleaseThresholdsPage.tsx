import { Button, Card, InputNumber, Table, Tag, Typography } from "antd";
import { ReleaseThresholdItem } from "../api/index";
import { useReleaseThresholdsPage } from "../hooks/useReleaseThresholdsPage";

function coverageLabel(r: ReleaseThresholdItem): string {
  const { is_fallback, score_profile, case_count } = r.coverage;
  const countSuffix = case_count > 0 ? ` · ${case_count} 题` : "";
  if (is_fallback) {
    return `score_profile=default（兜底）${countSuffix}`;
  }
  return `score_profile=${score_profile}${countSuffix}`;
}

export default function ReleaseThresholdsPage() {
  const rt = useReleaseThresholdsPage();

  const columns = [
    {
      title: "评分档",
      dataIndex: "label",
      width: 120,
      render: (label: string, r: ReleaseThresholdItem) => (
        <div style={{ lineHeight: 1.4 }}>
          <div>
            <Typography.Text strong>{label}</Typography.Text>
          </div>
          <Typography.Text type="secondary" style={{ fontSize: 12 }}>
            {r.profile}
          </Typography.Text>
        </div>
      ),
    },
    {
      title: "覆盖范围（score_profile）",
      key: "coverage",
      render: (_: unknown, r: ReleaseThresholdItem) => (
        <Tag color={r.coverage.is_fallback ? undefined : "blue"}>{coverageLabel(r)}</Tag>
      ),
    },
    {
      title: "满分上限",
      dataIndex: "max_total",
      width: 100,
      render: (v: number) => v.toFixed(2),
    },
    {
      title: "默认阈值",
      dataIndex: "default_threshold",
      width: 100,
      render: (v: number) => v.toFixed(2),
    },
    {
      title: "综合分上线阈值",
      width: 180,
      render: (_: unknown, r: ReleaseThresholdItem) => (
        <InputNumber
          min={0.01}
          max={r.max_total}
          step={0.01}
          value={rt.draft[r.profile]}
          onChange={(v) => rt.setProfileDraft(r.profile, (v as number) ?? r.default_threshold)}
          style={{ width: 120 }}
        />
      ),
    },
    {
      title: "状态",
      width: 120,
      render: (_: unknown, r: ReleaseThresholdItem) => {
        const changed = (rt.draft[r.profile] ?? r.effective) !== r.default_threshold;
        return changed ? <Tag color="orange">已自定义</Tag> : <Tag>默认</Tag>;
      },
    },
    {
      title: "",
      width: 90,
      render: (_: unknown, r: ReleaseThresholdItem) => (
        <Button
          size="small"
          type="link"
          disabled={rt.draft[r.profile] === r.default_threshold}
          onClick={() => rt.resetProfile(r.profile, r.default_threshold)}
        >
          恢复默认
        </Button>
      ),
    },
  ];

  return (
    <Card
      title="上线判定阈值（按场景）"
      extra={
        <Button type="primary" loading={rt.saving} onClick={rt.save}>
          保存
        </Button>
      }
    >
      <Table
        rowKey="profile"
        size="small"
        loading={rt.loading}
        columns={columns}
        dataSource={rt.rows}
        pagination={false}
      />
    </Card>
  );
}
