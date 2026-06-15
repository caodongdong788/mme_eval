import { useState } from "react";
import { Form } from "antd";

export function useEditModal<TId extends string | number = number>() {
  const [open, setOpen] = useState(false);
  const [editId, setEditId] = useState<TId | null>(null);
  const [saving, setSaving] = useState(false);
  const [form] = Form.useForm();

  const openCreate = (defaults?: Record<string, unknown>) => {
    setEditId(null);
    form.resetFields();
    if (defaults) form.setFieldsValue(defaults);
    setOpen(true);
  };

  const openEdit = (id: TId, values: Record<string, unknown>) => {
    setEditId(id);
    form.resetFields();
    form.setFieldsValue(values);
    setOpen(true);
  };

  const close = () => setOpen(false);

  return {
    open,
    setOpen,
    close,
    editId,
    isEditing: editId != null,
    saving,
    setSaving,
    form,
    openCreate,
    openEdit,
  };
}
