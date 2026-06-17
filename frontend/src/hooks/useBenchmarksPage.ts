import { useState } from "react";
import type { UploadFile } from "antd";
import { Form, message } from "antd";
import { api, Benchmark, CaseBrief } from "../api/index";
import { formatApiError } from "../utils/apiError";
import { useAsyncData } from "./useAsyncData";
import { useEditModal } from "./useEditModal";

export function useBenchmarksPage() {
  const { data: list, loading, error, reload } = useAsyncData(() => api.listBenchmarks(), []);
  const benchmarks = list ?? [];
  const editModal = useEditModal<number>();

  const [modalOpen, setModalOpen] = useState(false);
  const [replaceId, setReplaceId] = useState<number | null>(null);
  const [fileList, setFileList] = useState<UploadFile[]>([]);
  const [form] = Form.useForm();
  const [casesOpen, setCasesOpen] = useState(false);
  const [cases, setCases] = useState<CaseBrief[]>([]);
  const [casesTitle, setCasesTitle] = useState("");

  const builtin = benchmarks.find((b) => b.source === "builtin");
  const uploaded = benchmarks.filter((b) => b.source !== "builtin");

  const openCreate = () => {
    setReplaceId(null);
    setFileList([]);
    form.resetFields();
    setModalOpen(true);
  };

  const openReplace = (b: Benchmark) => {
    setReplaceId(b.id);
    setFileList([]);
    form.resetFields();
    setModalOpen(true);
  };

  const submit = async () => {
    const file = fileList[0]?.originFileObj;
    if (!file) {
      message.error("请选择一个 YAML 用例文件");
      return;
    }
    const fd = new FormData();
    fd.append("file", file);
    try {
      if (replaceId != null) {
        await api.replaceBenchmark(replaceId, fd);
        message.success("覆盖成功");
      } else {
        const values = await form.validateFields();
        fd.append("name", values.name);
        fd.append("description", values.description || "");
        await api.uploadBenchmark(fd);
        message.success("上传成功");
      }
      setModalOpen(false);
      setFileList([]);
      form.resetFields();
      reload();
    } catch (e: unknown) {
      message.error(formatApiError(e, "操作失败"));
    }
  };

  const viewCases = async (b: Benchmark) => {
    setCasesTitle(`${b.name}（${b.case_count} 条用例）`);
    setCasesOpen(true);
    setCases(await api.getBenchmarkCases(b.id));
  };

  const openEdit = (b: Benchmark) => {
    editModal.openEdit(b.id, { name: b.name, description: b.description });
  };

  const submitEdit = async () => {
    try {
      const v = await editModal.form.validateFields();
      await api.updateBenchmark(editModal.editId!, {
        name: v.name,
        description: v.description || "",
      });
      message.success("已保存");
      editModal.close();
      reload();
    } catch (e: unknown) {
      if ((e as { errorFields?: unknown })?.errorFields) return;
      message.error(formatApiError(e, "保存失败"));
    }
  };

  const deleteBenchmark = async (id: number) => {
    await api.deleteBenchmark(id);
    message.success("已删除");
    reload();
  };

  return {
    loading,
    loadError: error,
    builtin,
    uploaded,
    modalOpen,
    setModalOpen,
    replaceId,
    fileList,
    setFileList,
    form,
    casesOpen,
    setCasesOpen,
    cases,
    casesTitle,
    editForm: editModal.form,
    editOpen: editModal.open,
    setEditOpen: editModal.setOpen,
    openCreate,
    openReplace,
    submit,
    viewCases,
    openEdit,
    submitEdit,
    deleteBenchmark,
    reload,
  };
}
