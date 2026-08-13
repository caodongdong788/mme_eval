import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import { ConfigProvider } from "antd";
import zhCN from "antd/locale/zh_CN";
import "antd/dist/reset.css";
import "./styles.css";
import App from "./App";
import { themeConfig } from "./theme";
import { AuthProvider } from "./auth/AuthContext";
import { ErrorBoundary } from "./components/ErrorBoundary";

const CHUNK_RELOAD_KEY = "mme:chunk-reload-at";
const CHUNK_ERROR_PATTERN = /dynamically imported module|loading chunk|vite:preload/i;

/**
 * 发布会替换 Vite 的带 hash 分包文件。少数仍打开旧标签页的用户若刚好点击到
 * 懒加载页面，可能先请求到已不存在的旧 chunk；自动刷新一次即可拿到最新入口。
 */
function reloadOnceForChunkError(message: string): boolean {
  if (!CHUNK_ERROR_PATTERN.test(message)) return false;
  const lastReloadAt = Number(sessionStorage.getItem(CHUNK_RELOAD_KEY) || 0);
  if (Date.now() - lastReloadAt < 30_000) return false;
  sessionStorage.setItem(CHUNK_RELOAD_KEY, String(Date.now()));
  window.location.reload();
  return true;
}

window.addEventListener("vite:preloadError", (event) => {
  const message = event instanceof ErrorEvent ? event.message : String((event as CustomEvent).detail || "vite:preloadError");
  if (reloadOnceForChunkError(message)) event.preventDefault();
});

window.addEventListener("unhandledrejection", (event) => {
  const reason = event.reason;
  const message = reason instanceof Error ? reason.message : String(reason || "");
  if (reloadOnceForChunkError(message)) event.preventDefault();
});

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <ConfigProvider locale={zhCN} theme={themeConfig}>
      <BrowserRouter>
        <AuthProvider>
          <ErrorBoundary>
            <App />
          </ErrorBoundary>
        </AuthProvider>
      </BrowserRouter>
    </ConfigProvider>
  </React.StrictMode>
);
