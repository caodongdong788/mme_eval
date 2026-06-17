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
    // antd 作为单独 vendor chunk 体积较大但可被长期缓存并并行加载，调高告警阈值避免噪音。
    chunkSizeWarningLimit: 1100,
    rollupOptions: {
      output: {
        // 拆分第三方依赖，避免单体大包（react / antd / recharts 各自成 chunk）。
        manualChunks: {
          "vendor-react": ["react", "react-dom", "react-router-dom"],
          "vendor-antd": ["antd", "@ant-design/icons"],
          "vendor-charts": ["recharts"],
        },
      },
    },
  },
});
