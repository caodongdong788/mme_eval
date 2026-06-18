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
  const [casesBenchmark, setCasesBenchmark] = useState<Benchmark | null>(null);

  const [caseYamlOpen, setCaseYamlOpen] = useState(false);
  const [caseYamlLoading, setCaseYamlLoading] = useState(false);
  const [caseYamlSaving, setCaseYamlSaving] = useState(false);
  const [caseYamlText, setCaseYamlText] = useState("");
  const [caseYamlMeta, setCaseYamlMeta] = useState<{
    sampleId: string;
    subScenario: string;
    caseFile: string;
  } | null>(null);

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
    setCasesBenchmark(b);
    setCasesTitle(`${b.name}（${b.case_count} 条用例）`);
    setCasesOpen(true);
    setCases(await api.getBenchmarkCases(b.id));
  };

  const openCaseYaml = async (row: CaseBrief) => {
    if (!casesBenchmark) return;
    setCaseYamlOpen(true);
    setCaseYamlLoading(true);
    setCaseYamlText("");
    setCaseYamlMeta({
      sampleId: row.sample_id,
      subScenario: row.sub_scenario || row.sample_id,
      caseFile: "",
    });
    try {
      const res = await api.getBenchmarkCaseYaml(casesBenchmark.id, row.sample_id);
      setCaseYamlText(res.yaml_text);
      setCaseYamlMeta((m) =>
        m
          ? { ...m, caseFile: res.case_file }
          : {
              sampleId: row.sample_id,
              subScenario: row.sub_scenario || row.sample_id,
              caseFile: res.case_file,
            }
      );
    } catch (e: unknown) {
      message.error(formatApiError(e, "加载用例 YAML 失败"));
      setCaseYamlOpen(false);
    } finally {
      setCaseYamlLoading(false);
    }
  };

  const saveCaseYaml = async () => {
    if (!casesBenchmark || !caseYamlMeta) return;
    setCaseYamlSaving(true);
    try {
      const res = await api.saveBenchmarkCaseYaml(
        casesBenchmark.id,
        caseYamlMeta.sampleId,
        caseYamlText
      );
      setCaseYamlText(res.yaml_text);
      setCaseYamlMeta((m) => (m ? { ...m, caseFile: res.case_file } : m));
      message.success("用例已保存");
      setCases(await api.getBenchmarkCases(casesBenchmark.id));
      reload();
      setCaseYamlOpen(false);
    } catch (e: unknown) {
      message.error(formatApiError(e, "保存失败"));
    } finally {
      setCaseYamlSaving(false);
    }
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
    casesBenchmark,
    caseYamlOpen,
    setCaseYamlOpen,
    caseYamlLoading,
    caseYamlSaving,
    caseYamlText,
    setCaseYamlText,
    caseYamlMeta,
    openCaseYaml,
    saveCaseYaml,
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
