import { useEffect } from "react";
import { Form, Input, Modal, Popconfirm, Table, Tooltip } from "antd";
import {
  DeleteOutlined,
  DownloadOutlined,
  EditOutlined,
  FileSearchOutlined,
} from "@ant-design/icons";
import type { ColumnsType } from "antd/es/table";
import type { OnlineAnnotationPoolPath } from "../api/index";
import type { OnlineAnnotationPoolPathFormValues } from "../hooks/useOnlineEvalsPage";
import {
  DashTableActions,
  DashTableDangerLink,
  DashTableLink,
} from "./DashTableActions";

interface OnlineAnnotationPoolTableProps {
  rows: OnlineAnnotationPoolPath[];
  loading: boolean;
  exportingPathId: number | null;
  editingPath: OnlineAnnotationPoolPath | null;
  updatingPathId: number | null;
  deletingPathId: number | null;
  onExport: (pathId: number) => void;
  onOpenDetail: (row: OnlineAnnotationPoolPath) => void;
  onEdit: (row: OnlineAnnotationPoolPath) => void;
  onEditCancel: () => void;
  onEditSubmit: (pathId: number, values: OnlineAnnotationPoolPathFormValues) => Promise<boolean>;
  onDelete: (pathId: number) => void;
}

export function OnlineAnnotationPoolTable({
  rows,
  loading,
  exportingPathId,
  editingPath,
  updatingPathId,
  deletingPathId,
  onExport,
  onOpenDetail,
  onEdit,
  onEditCancel,
  onEditSubmit,
  onDelete,
}: OnlineAnnotationPoolTableProps) {
  const [editForm] = Form.useForm<OnlineAnnotationPoolPathFormValues>();
  const editing = Boolean(editingPath);

  useEffect(() => {
    if (editingPath) {
      editForm.setFieldsValue({
        path: editingPath.path,
        description: editingPath.description || "",
      });
    } else {
      editForm.resetFields();
    }
  }, [editForm, editingPath]);

  const submitEdit = async () => {
    if (!editingPath) return;
    const values = await editForm.validateFields();
    const ok = await onEditSubmit(editingPath.id, values);
    if (ok) onEditCancel();
  };

  const columns: ColumnsType<OnlineAnnotationPoolPath> = [
    {
      title: "标注集",
      dataIndex: "path",
      ellipsis: true,
      render: (v: string, row) => (
        <Tooltip title={v}>
          <DashTableLink disabled={editing} onClick={() => onOpenDetail(row)}>
            {v}
          </DashTableLink>
        </Tooltip>
      ),
    },
    {
      title: "描述",
      dataIndex: "description",
      ellipsis: true,
      render: (v: string) =>
        v ? <Tooltip title={v}>{v}</Tooltip> : <span style={{ color: "var(--muted)" }}>-</span>,
    },
    { title: "Case", dataIndex: "case_count", width: 90 },
    {
      title: "操作",
      key: "actions",
      width: 340,
      render: (_, row) => {
        const busy =
          exportingPathId === row.id ||
          updatingPathId === row.id ||
          deletingPathId === row.id;
        return (
          <DashTableActions>
            <DashTableLink disabled={busy || editing} onClick={() => onOpenDetail(row)}>
              <FileSearchOutlined /> 详情
            </DashTableLink>
            <DashTableLink
              disabled={row.case_count === 0 || busy || editing}
              onClick={() => onExport(row.id)}
            >
              <DownloadOutlined /> {exportingPathId === row.id ? "导出中" : "导出清单"}
            </DashTableLink>
            <DashTableLink disabled={busy || editing} onClick={() => onEdit(row)}>
              <EditOutlined /> {updatingPathId === row.id ? "保存中" : "编辑"}
            </DashTableLink>
            <Popconfirm
              title="确认删除该标注集？"
              description={
                row.case_count > 0
                  ? `将一并删除其中 ${row.case_count} 条 case 快照，且不可恢复。`
                  : "删除后不可恢复。"
              }
              okText="删除"
              cancelText="取消"
              okButtonProps={{ danger: true }}
              onConfirm={() => onDelete(row.id)}
              disabled={busy || editing}
            >
              <DashTableDangerLink disabled={busy || editing}>
                <DeleteOutlined /> {deletingPathId === row.id ? "删除中" : "删除"}
              </DashTableDangerLink>
            </Popconfirm>
          </DashTableActions>
        );
      },
    },
  ];

  return (
    <>
      <Table
        className="dash-table"
        rowKey="id"
        loading={loading}
        columns={columns}
        dataSource={rows}
        pagination={false}
      />
      <Modal
        title="编辑标注集"
        open={editing}
        okText="保存"
        cancelText="取消"
        confirmLoading={editingPath ? updatingPathId === editingPath.id : false}
        onOk={() => void submitEdit()}
        onCancel={onEditCancel}
        destroyOnHidden
      >
        <Form form={editForm} layout="vertical">
          <Form.Item
            name="path"
            label="标注集"
            rules={[{ required: true, message: "请输入标注集名称" }]}
          >
            <Input placeholder="如：骨健康满意样本" />
          </Form.Item>
          <Form.Item name="description" label="描述">
            <Input placeholder="标注集用途说明" />
          </Form.Item>
        </Form>
      </Modal>
    </>
  );
}
