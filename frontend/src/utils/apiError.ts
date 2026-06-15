// 统一解析后端错误响应为可读文案。
// FastAPI 的 `detail` 既可能是字符串（HTTPException），也可能是数组（422 校验错误，
// 形如 [{ loc, msg, type }, ...]）。直接拼到 message.error 会显示成 [object Object]。

interface ValidationItem {
  loc?: (string | number)[];
  msg?: string;
}

type ApiDetail = string | ValidationItem[] | Record<string, unknown> | undefined;

interface AxiosLikeError {
  response?: { data?: { detail?: ApiDetail } };
  message?: string;
}

function formatValidationItems(items: ValidationItem[]): string {
  return items
    .map((it) => {
      const field = Array.isArray(it.loc)
        ? it.loc.filter((p) => p !== "body").join(".")
        : "";
      const msg = it.msg ?? "校验失败";
      return field ? `${field}: ${msg}` : msg;
    })
    .filter(Boolean)
    .join("；");
}

// 将任意接口错误转为一句可展示的中文文案。
export function formatApiError(error: unknown, fallback = "操作失败"): string {
  const err = error as AxiosLikeError | undefined;
  const detail = err?.response?.data?.detail;

  if (typeof detail === "string" && detail.trim()) {
    return detail;
  }
  if (Array.isArray(detail) && detail.length > 0) {
    const text = formatValidationItems(detail as ValidationItem[]);
    if (text) return text;
  }
  if (detail && typeof detail === "object") {
    const msg = (detail as Record<string, unknown>).msg;
    if (typeof msg === "string" && msg.trim()) return msg;
  }
  if (typeof err?.message === "string" && err.message.trim()) {
    return err.message;
  }
  return fallback;
}
