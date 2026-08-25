// 面向用户的统一中文错误说明。技术原文只写入浏览器控制台和服务端日志。

import { DIM_LABEL } from "../labels";

interface ValidationItem {
  loc?: (string | number)[];
  msg?: string;
  type?: string;
  ctx?: Record<string, unknown>;
}

type ApiDetail = string | ValidationItem[] | Record<string, unknown> | undefined;

interface AxiosLikeError {
  response?: { status?: number; data?: { detail?: ApiDetail } };
  message?: string;
}

const FIELD_LABEL: Record<string, string> = {
  sample_id: "用例编号",
  scenario: "场景",
  level: "难度级别",
  evaluation: "评测配置",
  dimension_criteria: "八维评测要求",
  criteria: "评测要求",
  reference_answers: "推荐回答",
  guidelines: "指南扣分点",
  max_score: "最高扣分",
  dimension: "关联维度",
};

function locationLabel(loc?: (string | number)[]): string {
  const parts = (loc || []).map(String).filter((part) => !["body", "query", "path"].includes(part));
  const dimensionKey = parts.find((part) => DIM_LABEL[part]);
  const lastPart = parts.length ? parts[parts.length - 1] : "";
  const field = FIELD_LABEL[lastPart] || lastPart || "数据";
  return dimensionKey ? `${DIM_LABEL[dimensionKey]}的“${field}”` : field;
}

function formatValidationItem(item: ValidationItem): string {
  const field = locationLabel(item.loc);
  const last = item.loc?.length ? item.loc[item.loc.length - 1] : undefined;
  const type = item.type || "";
  if (last === "criteria" && ["too_short", "list_too_short", "value_error"].includes(type)) {
    const minimum = Number(item.ctx?.min_length || 1);
    return `${field}至少需要保留 ${minimum} 条；如果该维度没有补充要求，请删除整个空维度`;
  }
  if (type === "missing") return `缺少必填项“${field}”`;
  if (["string_type", "string_unicode"].includes(type)) return `${field}必须填写文本`;
  if (["int_type", "int_parsing"].includes(type)) return `${field}必须填写整数`;
  if (type === "list_type") return `${field}必须是列表`;

  const msg = String(item.msg || "").replace(/^Value error,\s*/i, "").trim();
  return /[\u4e00-\u9fff]/.test(msg)
    ? `${field}：${msg}`
    : `${field}填写不符合要求，请检查后重试`;
}

function formatValidationItems(items: ValidationItem[]): string {
  return [...new Set(items.map(formatValidationItem).filter(Boolean))].join("；");
}

/** 把接口、模型和浏览器异常转成可操作的中文说明。 */
export function humanizeErrorText(
  value: unknown,
  fallback = "操作失败，请稍后重试",
  status?: number,
): string {
  const text = String(value || "").trim();

  if (/dimension_criteria\.([a-z_]+)\.criteria[\s\S]*at least 1 item|criteria[\s\S]*too_short/i.test(text)) {
    const key = text.match(/dimension_criteria\.([a-z_]+)\.criteria/i)?.[1] || "";
    const dimension = DIM_LABEL[key] || "对应维度";
    return `用例校验失败：${dimension}的“评测要求”至少需要保留 1 条；如果该维度没有补充要求，请删除整个空维度`;
  }
  if (/expecting value|json.*decode|invalid json/i.test(text)) {
    return "判分模型没有返回可解析的结果，请稍后重试；如持续出现，请检查模型配置";
  }
  if (/internalservererror|internal_server_error|an internal error has occurred/i.test(text)) {
    return "模型服务内部处理失败，请稍后重试；如持续出现，请更换模型或检查模型配置";
  }
  if (/badrequesterror|invalid request error/i.test(text)) {
    return "模型服务拒绝了本次请求，请检查模型参数与输入长度后重试";
  }
  if (/timeout|timed out|etimedout/i.test(text) || status === 504) {
    return "请求处理超时，请稍后重试";
  }
  if (/network error|failed to fetch|econnrefused|connection refused/i.test(text)) {
    return "暂时无法连接服务，请检查网络后重试";
  }
  if (status === 401 || /unauthorized/i.test(text)) return "登录已过期，请重新登录";
  if (status === 403 || /forbidden/i.test(text)) return "当前账号没有执行此操作的权限";
  if (status === 404 || /^not found$/i.test(text)) return "没有找到对应的数据，可能已被删除或链接已失效";
  // 409 在平台中通常附带可行动的中文原因（例如名称重复、已有进行中的任务）。
  // 不能用一条泛化的“数据状态变化”覆盖它，否则用户无法判断下一步该怎么做。
  if (status === 409) {
    if (text && /[\u4e00-\u9fff]/.test(text)) return text;
    return "当前操作暂时无法完成，相关内容可能已被更新；请刷新页面后重试";
  }
  if (status === 429 || /rate limit|too many requests/i.test(text)) return "请求过于频繁，请稍后重试";
  if (status === 502 || /bad gateway|httpexception:\s*502/i.test(text)) return "上游服务暂时不可用，请稍后重试";
  if (status === 503 || /service unavailable/i.test(text)) return "服务正在启动或维护中，请稍后重试";
  if (status && status >= 500) return "服务器处理请求时发生异常，请稍后重试";
  if (/validation error/i.test(text)) return "数据校验失败，请检查填写内容后重试";

  // 已经是后端整理过的中文说明时直接展示。
  if (text && /[\u4e00-\u9fff]/.test(text)) return text;
  return fallback;
}

// 将任意接口错误转为一句可展示的中文文案。
export function formatApiError(error: unknown, fallback = "操作失败，请稍后重试"): string {
  const err = error as AxiosLikeError | undefined;
  const detail = err?.response?.data?.detail;
  const status = err?.response?.status;

  if (Array.isArray(detail) && detail.length > 0) {
    const text = formatValidationItems(detail as ValidationItem[]);
    if (text) return `请求参数校验失败：${text}`;
  }
  if (detail && typeof detail === "object") {
    const msg = (detail as Record<string, unknown>).msg;
    if (typeof msg === "string" && msg.trim()) return humanizeErrorText(msg, fallback, status);
  }
  if (typeof detail === "string" && detail.trim()) {
    return humanizeErrorText(detail, fallback, status);
  }
  return humanizeErrorText(err?.message, fallback, status);
}
