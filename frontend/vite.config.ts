/// <reference types="vitest/config" />
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// 开发时把 /api 代理到 FastAPI 后端（默认 8000）。
export default defineConfig({
  plugins: [react()],
  test: {
    environment: "jsdom",
    setupFiles: "./src/test/setup.ts",
    css: true,
    include: ["src/**/*.{test,spec}.{ts,tsx}"],
    exclude: ["scripts/**", "node_modules/**"],
  },
  server: {
    port: 5173,
    proxy: {
      "/api": {
        target: process.env.MEDEVAL_API_URL || "http://localhost:8000",
        changeOrigin: true,
      },
    },
  },
  build: {
    outDir: "dist",
    rollupOptions: {
      output: {
        // React 是所有页面共享的运行时；其余依赖交给 Vite 按路由依赖自动
        // 拆分，避免把懒加载页面使用的组件强行聚合为首屏必载大包。
        manualChunks(id) {
          if (!id.includes("node_modules")) return undefined;
          if (/node_modules\/(react|react-dom|react-router|react-router-dom)\//.test(id)) {
            return "vendor-react";
          }
          return undefined;
        },
      },
    },
  },
});
