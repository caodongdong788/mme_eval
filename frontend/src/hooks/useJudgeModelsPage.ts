import { message } from "antd";
import { api, JudgeModel } from "../api/index";
import { formatApiError } from "../utils/apiError";
import { useAsyncData } from "./useAsyncData";
import { useEditModal } from "./useEditModal";

export function useJudgeModelsPage() {
  const { data: list, loading, error, reload } = useAsyncData(() => api.listJudgeModels(), []);
  const models = list ?? [];
  const modal = useEditModal<number>();

  const openCreate = () => modal.openCreate({ provider: "openai", pairwise_concurrency: 4 });

  const openEdit = (m: JudgeModel) => {
    modal.openEdit(m.id, {
      name: m.name,
      provider: m.provider || "openai",
      model: m.model,
      base_url: m.base_url,
      api_version: m.api_version,
      temperature: m.temperature ?? undefined,
      pairwise_concurrency: m.pairwise_concurrency ?? 4,
      api_key: "",
    });
  };

  const submit = async () => {
    let v: Record<string, unknown>;
    try {
      v = await modal.form.validateFields();
    } catch {
      return;
    }
    const payload = {
      name: (v.name as string)?.trim(),
      provider: (v.provider as string) || "openai",
      model: (v.model as string)?.trim(),
      base_url: (v.base_url as string) || undefined,
      api_version: (v.api_version as string) || undefined,
      temperature: (v.temperature as number) ?? undefined,
      pairwise_concurrency: (v.pairwise_concurrency as number) ?? undefined,
      api_key: v.api_key ? (v.api_key as string) : undefined,
    };
    modal.setSaving(true);
    try {
      if (modal.editId != null) {
        await api.updateJudgeModel(modal.editId, payload);
        message.success("已保存");
      } else {
        await api.createJudgeModel(payload);
        message.success("已创建");
      }
      modal.close();
      reload();
    } catch (e: unknown) {
      message.error(formatApiError(e, "保存失败"));
    } finally {
      modal.setSaving(false);
    }
  };

  const deleteModel = async (id: number) => {
    await api.deleteJudgeModel(id);
    message.success("已删除");
    reload();
  };

  return {
    models,
    loading,
    loadError: error,
    reload,
    open: modal.open,
    setOpen: modal.setOpen,
    editId: modal.editId,
    saving: modal.saving,
    form: modal.form,
    openCreate,
    openEdit,
    submit,
    deleteModel,
  };
}
