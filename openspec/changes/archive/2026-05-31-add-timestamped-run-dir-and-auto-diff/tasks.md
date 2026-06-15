# Tasks

## 1. 唯一输出目录
- [x] 1.1 在 `cli.py` 生成 `run_slug = f"{run.name}_{毫秒Unix时间戳}"`，传入 `build_report(run_name=...)`，使 `out_dir = outputs/<run_slug>`
- [x] 1.2 验证同名 `run.name` 连跑两次产出两个独立目录、互不覆盖

## 2. 版本对比解析
- [x] 2.1 新增 `_find_previous_run(outputs_dir, current_dir)`：按 `report.json` mtime 取除本次外最近一次
- [x] 2.2 新增 CLI `--diff-against` flag（auto / none / 具体目录名）
- [x] 2.3 实现优先级解析：CLI > config.reporter.diff_against > 默认自动；none/off 关闭；指定版本不存在时提示并跳过
- [x] 2.4 命中目标时先写当前 JSON 再 diff、摘要嵌入 Markdown

## 3. 文档与配置同步
- [x] 3.1 更新 `config.yaml` 的 `reporter.diff_against` 注释
- [x] 3.2 更新 `AGENTS.md`（常用命令 / 目录地图 / 易踩的坑）
- [x] 3.3 更新 `README.md` 启动方式与输出目录说明
- [x] 3.4 同步 `openspec/specs/evaluation-cli/spec.md`
