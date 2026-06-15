## 1. 死代码清理

- [x] 1.1 删 `medeval/reporter/lark_publisher.py::publish_report_file`
- [x] 1.2 删 `server/auth.py::require_user`
- [x] 1.3 前端 `RunDashboardPage.tsx` 删 `gradeData` + `{gradeData.length > 0 && null}`
- [x] 1.4 前端 `api.ts` `http` 收为模块内 const（去 export）
- [x] 1.5 前端 `RunsPage.tsx` 去掉 `reload()` 的 `return active.length`

## 2. 文档同步

- [x] 2.1 `README.md`：评测平台章 + SSO/导出 + 延迟 + 新能力清单 + 42→71 + profile 表键名 + 品牌
- [x] 2.2 `AGENTS.md`：内核/平台区分 + 平台命令 + profile 自适应 + hard_gate_passed 轴 + 品牌
- [x] 2.3 `.env.example` / `server/README.md`：品牌 + DATABASE_URL 一致化
- [x] 2.4 `openspec/specs/eval-platform-service/spec.md`：`DATABASE_URL`→`MEDEVAL_DATABASE_URL`
- [x] 2.5 平台/飞书 spec 的 `## Purpose: TBD` 补写

## 3. 收尾

- [x] 3.1 全量 `pytest` 绿
- [x] 3.2 前端 `tsc` 零报错
- [x] 3.3 `medeval run --config config.yaml --dry-run`
- [x] 3.4 刷新图谱 + `openspec validate --strict` 通过后 `openspec archive`
