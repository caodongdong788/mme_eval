import { Descriptions, Drawer, Space, Tag } from "antd";
import type { BenchmarkCoverage } from "../api";

interface BenchmarkCoverageDrawerProps {
  coverage: BenchmarkCoverage | null;
  loading: boolean;
  open: boolean;
  onClose: () => void;
}

export function BenchmarkCoverageDrawer({
  coverage,
  loading,
  open,
  onClose,
}: BenchmarkCoverageDrawerProps) {
  return (
    <Drawer title="评测集覆盖度" width={640} open={open} onClose={onClose}>
      {loading ? "正在统计…" : coverage ? (
        <Space direction="vertical" size={18} style={{ width: "100%" }}>
          <Descriptions size="small" column={1} bordered title={`共 ${coverage.total} 条用例`}>
            {Object.entries(coverage.coverage_rate).map(([key, value]) => (
              <Descriptions.Item key={key} label={key}>{(value * 100).toFixed(0)}%</Descriptions.Item>
            ))}
          </Descriptions>
          {[
            ["八维评分覆盖", coverage.dimensions],
            ["断言类型", coverage.assertion_types],
            ["评测机制", coverage.mechanisms],
            ["场景分布", coverage.by_scenario],
          ].map(([title, values]) => (
            <div key={String(title)}>
              <div style={{ marginBottom: 8, fontWeight: 600 }}>{String(title)}</div>
              {Object.entries(values as Record<string, number>).map(([key, value]) => (
                <Tag key={key}>{key} · {value}</Tag>
              ))}
            </div>
          ))}
        </Space>
      ) : <span>暂无统计数据</span>}
    </Drawer>
  );
}
