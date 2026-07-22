import { Popconfirm, Typography } from "antd";
import { DashTableDangerLink, DashTableLink } from "./DashTableActions";
import type { CaseBrief } from "../api/types";

interface BenchmarkCaseColumnsOptions {
  isBuiltin: boolean;
  onOpenCase: (row: CaseBrief) => void;
  onDeleteCase: (row: CaseBrief) => void;
}

export function shortCaseId(sampleId: string) {
  const match = sampleId.match(/(?:^|_)(case_\d+)$/i);
  return match?.[1] || sampleId;
}

export function createBenchmarkCaseColumns({
  isBuiltin,
  onOpenCase,
  onDeleteCase,
}: BenchmarkCaseColumnsOptions) {
  return [
    {
      title: "Case ID",
      dataIndex: "sample_id",
      ellipsis: true,
      render: (_: string, row: CaseBrief) => (
        <DashTableLink onClick={() => onOpenCase(row)}>{shortCaseId(row.sample_id)}</DashTableLink>
      ),
    },
    { title: "场景", dataIndex: "scenario" },
    { title: "Level", dataIndex: "level", width: 80 },
    {
      title: "Case 类型",
      dataIndex: "case_type",
      width: 110,
      render: (value: string) => value || <Typography.Text type="secondary">—</Typography.Text>,
    },
    {
      title: "操作",
      width: 90,
      render: (_: unknown, row: CaseBrief) =>
        isBuiltin ? (
          <Typography.Text type="secondary">-</Typography.Text>
        ) : (
          <Popconfirm title="确认删除该 case?" onConfirm={() => onDeleteCase(row)}>
            <DashTableDangerLink>删除</DashTableDangerLink>
          </Popconfirm>
        ),
    },
  ];
}
