import { Popconfirm, Typography } from "antd";
import { DashTableDangerLink, DashTableLink } from "./DashTableActions";
import { PROFILE_LABEL } from "../labels";
import type { CaseBrief } from "../api/types";

interface BenchmarkCaseColumnsOptions {
  isOnlineCase: boolean;
  isBuiltin: boolean;
  onOpenCase: (row: CaseBrief) => void;
  onDeleteCase: (row: CaseBrief) => void;
}

export function createBenchmarkCaseColumns({
  isOnlineCase,
  isBuiltin,
  onOpenCase,
  onDeleteCase,
}: BenchmarkCaseColumnsOptions) {
  return [
    {
      title: "子场景",
      dataIndex: "sub_scenario",
      ellipsis: true,
      render: (text: string, row: CaseBrief) => (
        <DashTableLink onClick={() => onOpenCase(row)}>{text || row.sample_id}</DashTableLink>
      ),
    },
    ...(isOnlineCase
      ? []
      : [
          { title: "场景", dataIndex: "scenario" },
          { title: "Level", dataIndex: "level", width: 80 },
          {
            title: "Profile",
            dataIndex: "score_profile",
            width: 120,
            render: (profile: string) => PROFILE_LABEL[profile] || profile,
          },
        ]),
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
