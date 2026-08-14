import { useMemo, useState } from "react";
import type { UploadFile } from "antd";
import { Form, message } from "antd";
import { api, Benchmark, BenchmarkCaseContent, BenchmarkCoverage, CaseBrief } from "../api/index";
import { formatApiError } from "../utils/apiError";
import { useAsyncData } from "./useAsyncData";
import { useEditModal } from "./useEditModal";
import { shortCaseId } from "../components/BenchmarkCaseColumns";
import {
  buildBenchmarkCaseFilterValueOptions,
  type CaseFilterCondition,
  filterBenchmarkCaseRows,
  isActiveCaseFilter,
} from "../utils/caseFilters";

export function useBenchmarksPage() {
  const { data: list, loading, error, reload } = useAsyncData(() => api.listBenchmarks(), []);
  const benchmarks = list ?? [];
  const editModal = useEditModal<number>();

  const [modalOpen, setModalOpen] = useState(false);
  const [replaceId, setReplaceId] = useState<number | null>(null);
  const [appendId, setAppendId] = useState<number | null>(null);
  const [fileList, setFileList] = useState<UploadFile[]>([]);
  const [form] = Form.useForm();
  const [casesOpen, setCasesOpen] = useState(false);
  const [cases, setCases] = useState<CaseBrief[]>([]);
  const [casesLoading, setCasesLoading] = useState(false);
  const [casesError, setCasesError] = useState<string | null>(null);
  const [casesTitle, setCasesTitle] = useState("");
  const [casesBenchmark, setCasesBenchmark] = useState<Benchmark | null>(null);
  const [caseFilterConditions, setCaseFilterConditions] = useState<CaseFilterCondition[]>([]);
  const [coverage, setCoverage] = useState<BenchmarkCoverage | null>(null);
  const [coverageOpen, setCoverageOpen] = useState(false);
  const [coverageLoading, setCoverageLoading] = useState(false);

  const [caseYamlOpen, setCaseYamlOpen] = useState(false);
  const [caseYamlLoading, setCaseYamlLoading] = useState(false);
  const [caseYamlSaving, setCaseYamlSaving] = useState(false);
  const [caseContent, setCaseContent] = useState<BenchmarkCaseContent | null>(null);
  const [caseYamlMeta, setCaseYamlMeta] = useState<{
    sampleId: string;
    caseId: string;
    caseFile: string;
  } | null>(null);

  const builtin = benchmarks.find((b) => b.source === "builtin");
  const uploaded = benchmarks.filter((b) => b.source !== "builtin");
  const shownCases = useMemo(
    () =>
      filterBenchmarkCaseRows(
        cases,
        caseFilterConditions,
        casesBenchmark?.source === "builtin"
      ),
    [caseFilterConditions, cases, casesBenchmark?.source]
  );
  const caseFilterValueOptions = useMemo(
    () => buildBenchmarkCaseFilterValueOptions(cases),
    [cases]
  );
  const caseActiveFilterCount = caseFilterConditions.filter(isActiveCaseFilter).length;

  const openCreate = () => {
    setReplaceId(null);
    setAppendId(null);
    setFileList([]);
    form.resetFields();
    form.setFieldsValue({ default_evaluation_mode: "single_turn", suite_type: "capability" });
    setModalOpen(true);
  };

  const openReplace = (b: Benchmark) => {
    setReplaceId(b.id);
    setAppendId(null);
    setFileList([]);
    form.resetFields();
    form.setFieldsValue({
      default_evaluation_mode: b.default_evaluation_mode || "single_turn",
      suite_type: b.suite_type || "capability",
    });
    setModalOpen(true);
  };

  const openAppend = (b: Benchmark) => {
    setReplaceId(null);
    setAppendId(b.id);
    setFileList([]);
    form.resetFields();
    setModalOpen(true);
  };

  const submit = async () => {
    try {
      const values = await form.validateFields();
      const file = fileList[0]?.originFileObj;
      if (!file) {
        message.error("请选择一个 YAML / ZIP 用例文件");
        return;
      }
      const fd = new FormData();
      fd.append("file", file);
      // 后端仍保留来源字段以兼容历史数据；页面不再展示线上/线下的概念。
      fd.append("source", "offline");
      if (appendId == null) {
        fd.append("default_evaluation_mode", values.default_evaluation_mode || "single_turn");
        fd.append("suite_type", values.suite_type || "capability");
      }
      if (appendId != null) {
        await api.appendBenchmark(appendId, fd);
        message.success("追加成功");
      } else if (replaceId != null) {
        await api.replaceBenchmark(replaceId, fd);
        message.success("覆盖成功");
      } else {
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
    setCases([]);
    setCaseFilterConditions([]);
    setCasesLoading(true);
    setCasesError(null);
    try {
      const nextCases = await api.getBenchmarkCases(b.id);
      setCases(nextCases);
      setCasesTitle(`${b.name}（${nextCases.length} 条用例）`);
    } catch (e: unknown) {
      setCasesError(formatApiError(e, "用例解析失败"));
    } finally {
      setCasesLoading(false);
    }
  };

  const viewCoverage = async (b: Benchmark) => {
    setCoverageOpen(true);
    setCoverage(null);
    setCoverageLoading(true);
    try {
      setCoverage(await api.getBenchmarkCoverage(b.id));
    } catch (e: unknown) {
      message.error(formatApiError(e, "读取覆盖度失败"));
    } finally {
      setCoverageLoading(false);
    }
  };

  const openCaseYaml = async (row: CaseBrief) => {
    if (!casesBenchmark) return;
    setCaseYamlOpen(true);
    setCaseYamlLoading(true);
    setCaseContent(null);
    setCaseYamlMeta({
      sampleId: row.sample_id,
      caseId: shortCaseId(row.sample_id),
      caseFile: "",
    });
    try {
      const res = await api.getBenchmarkCaseContent(casesBenchmark.id, row.sample_id);
      setCaseContent(res);
      setCaseYamlMeta((m) =>
        m
          ? { ...m, caseFile: res.case_file }
          : {
              sampleId: row.sample_id,
              caseId: shortCaseId(row.sample_id),
              caseFile: res.case_file,
            }
      );
    } catch (e: unknown) {
      message.error(formatApiError(e, "加载用例失败"));
      setCaseYamlOpen(false);
    } finally {
      setCaseYamlLoading(false);
    }
  };

  const saveCaseYaml = async () => {
    if (!casesBenchmark || !caseYamlMeta || !caseContent) return;
    setCaseYamlSaving(true);
    try {
      const res = await api.saveBenchmarkCaseContent(
        casesBenchmark.id,
        caseYamlMeta.sampleId,
        caseContent.case
      );
      setCaseContent(res);
      setCaseYamlMeta((m) => (m ? { ...m, caseFile: res.case_file } : m));
      message.success("用例已保存");
      const nextCases = await api.getBenchmarkCases(casesBenchmark.id);
      setCases(nextCases);
      setCasesTitle(`${casesBenchmark.name}（${nextCases.length} 条用例）`);
      reload();
      setCaseYamlOpen(false);
    } catch (e: unknown) {
      message.error(formatApiError(e, "保存失败"));
    } finally {
      setCaseYamlSaving(false);
    }
  };

  const loadCurrentCaseSourceYaml = async () => {
    if (!casesBenchmark || !caseYamlMeta) return "";
    const sourceYaml = await api.getBenchmarkCaseYaml(
      casesBenchmark.id,
      caseYamlMeta.sampleId
    );
    return sourceYaml.yaml_text;
  };

  const deleteCase = async (row: CaseBrief) => {
    if (!casesBenchmark) return;
    try {
      await api.deleteBenchmarkCase(casesBenchmark.id, row.sample_id);
      message.success("用例已删除");
      const nextCases = await api.getBenchmarkCases(casesBenchmark.id);
      setCases(nextCases);
      setCasesTitle(`${casesBenchmark.name}（${nextCases.length} 条用例）`);
      if (caseYamlMeta?.sampleId === row.sample_id) {
        setCaseYamlOpen(false);
        setCaseContent(null);
        setCaseYamlMeta(null);
      }
      reload();
    } catch (e: unknown) {
      message.error(formatApiError(e, "删除用例失败"));
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
    appendId,
    fileList,
    setFileList,
    form,
    casesOpen,
    setCasesOpen,
    cases,
    shownCases,
    caseFilterConditions,
    setCaseFilterConditions,
    caseFilterValueOptions,
    caseActiveFilterCount,
    casesLoading,
    casesError,
    casesTitle,
    casesBenchmark,
    coverage,
    coverageOpen,
    coverageLoading,
    setCoverageOpen,
    caseYamlOpen,
    setCaseYamlOpen,
    caseYamlLoading,
    caseYamlSaving,
    caseContent,
    setCaseContent,
    caseYamlMeta,
    openCaseYaml,
    saveCaseYaml,
    loadCurrentCaseSourceYaml,
    deleteCase,
    editForm: editModal.form,
    editOpen: editModal.open,
    setEditOpen: editModal.setOpen,
    openCreate,
    openReplace,
    openAppend,
    submit,
    viewCases,
    viewCoverage,
    openEdit,
    submitEdit,
    deleteBenchmark,
    reload,
  };
}
