const DEFAULT_RETURN_TO = "/runs";

/** 只允许回到当前站点内的前端页面，防止登录参数被用于开放重定向。 */
export function sanitizeReturnTo(value?: string | null): string {
  if (!value || !value.startsWith("/") || value.startsWith("//") || value.includes("\\")) {
    return DEFAULT_RETURN_TO;
  }
  try {
    const target = new URL(value, window.location.origin);
    if (target.origin !== window.location.origin || target.pathname === "/login") {
      return DEFAULT_RETURN_TO;
    }
    return `${target.pathname}${target.search}${target.hash}`;
  } catch {
    return DEFAULT_RETURN_TO;
  }
}

export function currentReturnTo(): string {
  return sanitizeReturnTo(
    `${window.location.pathname}${window.location.search}${window.location.hash}`
  );
}

export function loginPath(returnTo = currentReturnTo()): string {
  return `/login?redirect_to=${encodeURIComponent(sanitizeReturnTo(returnTo))}`;
}

export function feishuLoginPath(returnTo: string): string {
  return `/api/auth/feishu/login?redirect_to=${encodeURIComponent(
    sanitizeReturnTo(returnTo)
  )}`;
}
