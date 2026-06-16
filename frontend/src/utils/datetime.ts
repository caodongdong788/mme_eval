/** 平台 API 时间戳：服务端存 UTC，JSON 可能为无时区 ISO；统一按 UTC 解析再转本地展示。 */

const HAS_TZ = /[zZ]$|[+-]\d{2}:\d{2}$/;

export function parseApiDateTime(value: string): Date {
  const trimmed = value.trim();
  if (!trimmed) return new Date(NaN);
  if (HAS_TZ.test(trimmed)) return new Date(trimmed);
  return new Date(`${trimmed}Z`);
}

export function formatApiDateTime(value?: string | null): string {
  if (!value) return "-";
  const d = parseApiDateTime(value);
  return Number.isNaN(d.getTime()) ? "-" : d.toLocaleString();
}

/** 人审卡片等紧凑展示：YYYY-MM-DD HH:mm（本地时区）。 */
export function formatApiDateTimeShort(value?: string | null): string {
  if (!value) return "";
  const d = parseApiDateTime(value);
  if (Number.isNaN(d.getTime())) return "";
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`;
}
