# MIGRATION.md — medeval 换电脑迁移与环境重建指南

> 本文件给 **AI 模型 / agent** 看：在一台新电脑上，按本文件**从上到下顺序执行**，即可让本仓库恢复到可运行状态。本仓库 = **判分内核 medeval（CLI）** + **MME · Agent 评测平台（Web：`server/` 后端 + `frontend/` 看板）**，并（按需）复刻 AI 辅助工作流（graphify 代码图谱、OpenSpec、飞书发布）。
>
> **执行约定**：每一步给出命令 + 验证方式。若某步标注「⭐ 必需」务必执行；标注「按需」的根据用户目标决定是否执行（见文末「按目标取舍」）。遇到验证失败先排查再继续，不要跳步。
>
> **版本管理**：本仓库已 `git init`（分支 `main`）。换机可用 `git clone` / `git pull`，或附录 A 的 `rsync` 拷贝目录；推送远程见 §8.1。

---

## TL;DR — 最小可运行（模型可直接逐行执行）

> 适用：已把项目目录拷到新电脑，只想尽快跑起来。前提 Python ≥ 3.10、Node ≥ 20 已就绪（否则先看步骤 0）。在**项目根目录**（含 `pyproject.toml`）执行：

```bash
# 1. Python 环境 + 依赖（CLI + 测试 + LLM judge + 平台后端 + Langfuse 追踪，一次装齐）
python3 -m venv .venv
source .venv/bin/activate                  # Windows: .venv\Scripts\activate
pip install -e ".[dev,llm-openai,server,langfuse]"   # langfuse 不要可省；省了追踪自动 no-op

# 2. 前端依赖（仅跑 Web 平台才需要）
cd frontend && npm install && cd ..

# 3. 验证 CLI 可用（不打真实 API）
medeval --help && medeval validate && medeval list-cases
pytest -m golden

# 4a. 跑 CLI 评测（密钥见步骤 2；config.yaml 已内联兜底 key，可直接跑）
medeval run --config config.yaml --limit 1 --dry-run   # 先 dry-run 确认装配无误
# medeval run --config config.yaml                      # 正式跑

# 4b. 或启动 Web 平台（后端 :8000 + 前端 :5173）
# scripts/dev_platform.sh
```

- 跑通 CLI 评测：执行 1 → 3 → 4a 即可（前端可跳过）。
- 跑 Web 平台：执行 1 → 2 → 4b。
- 密钥说明、graphify/飞书等可选项见下方分步章节。

---

## 0. 前置确认（先判断当前状态）

```bash
python3 --version        # 需要 ≥ 3.10
node -v                  # 需要 ≥ 20（前端 Vite 构建 / npx / lark-cli 都依赖）
which pipx               # graphify 用 pipx 安装
```

- Python < 3.10 或缺失 → 先装 Python ≥ 3.10。
- Node 缺失或 < 20 → 先装 Node.js ≥ 20（建议 nvm）。评测平台前端（Vite 5 + React 18）与 lark-cli 都依赖它。
- `pipx` 缺失 → 执行：
  ```bash
  python3 -m pip install --user pipx
  python3 -m pipx ensurepath
  ```
  装完**重开终端**，让 `~/.local/bin` 进入 PATH。

---

## 1. ⭐ 必需：恢复项目代码并重建运行环境

> 前提：项目目录已经拷到新电脑（拷贝时应已排除 `.venv` / `__pycache__` / `*.egg-info` / `.pytest_cache` / `frontend/node_modules` / `.DS_Store`，这些都在本机重建，绝不跨机器拷贝）。

进入项目根目录（含 `pyproject.toml` 的那一层），然后：

```bash
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -e ".[dev,llm-openai,server,langfuse]"   # 纯 CLI 可去掉 server,langfuse
```

> 若**只跑 CLI 评测、不用 Web 平台与 Langfuse 追踪**，可改为 `pip install -e ".[dev,llm-openai]"`；要跑平台见步骤 3（至少补 `server`；追踪需 `langfuse` extra）。

**验证**：

```bash
medeval --help                     # 能打印 CLI 帮助即安装成功
medeval validate                   # 校验用例库 schema
medeval list-cases                 # 应列出乳腺癌 benchmark 用例
pytest -m golden                   # HardGate 黄金集回归应通过
```

---

## 2. ⭐ 必需（运行评测前）：配置密钥与环境变量

`config.yaml` 的每个模型端点用 `api_key_env` 指定**环境变量名**，运行时**优先读该环境变量**，读不到才回退到文件里内联的 `api_key`。当前实际用到的环境变量：

| 环境变量 | 用途 | config.yaml 位置 |
|---------|------|-----------------|
| `DOUBAO_API_KEY` | 被测 chatbot（豆包 / 火山方舟，`openai_compat` adapter） | `adapter.openai_compat.api_key_env` |
| `AIDP_API_KEY` | LLM-as-Judge / scoring_point / 语义裁决（也供 `scripts/aidp_proxy.py`） | `judges.*.api_key_env` |
| `MEDBOT_TOKEN` | 仅当 `adapter.type=http` 且 header 用到 `${MEDBOT_TOKEN}` 时 | `adapter.http`（可选） |

设置方式（写进 shell 配置，如 `~/.zshrc` / `~/.bashrc`，然后 `source`）：

```bash
export DOUBAO_API_KEY="<被测 bot 的 key>"
export AIDP_API_KEY="<judge 用的 key>"
```

> ⚠️ **安全提示（重要）**：当前 `config.yaml` 里**内联了真实 `api_key` 作为兜底**——所以即使不设上面环境变量，把项目拷到新电脑后也能**直接跑通**（密钥随文件一起过来了）。但真实密钥明文留在 `config.yaml` 并被拷贝/打包到处传，有泄露风险。迁移后建议：把 `config.yaml` 内联的 `api_key` 清空、改为只用 `api_key_env` 环境变量；旧 key 视情况轮换。

- 评测要有意义：把 `adapter.openai_compat.system_prompt` 换成产品真实 prompt。
- 复现性默认：`temperature: 0.0`、`run.repeat: 1`（基线对比可用 `--repeat 3`）。

**验证**：先小规模试跑（dry-run 不打真实 API，只验证装配）

```bash
medeval run --config config.yaml --limit 1 --dry-run
```

---

## 3. 按需：启动评测平台（Web · server + frontend）

> 只在你想用网页发起评测 / 看跨 run 趋势看板时执行；纯跑 CLI 评测可跳过。平台后端 FastAPI（`server.app:app`）复用判分内核的 `evaluate()`，前端 React + Vite + Ant Design。

**3.1 安装后端依赖**（步骤 1 若没带 `server` / `langfuse` extra，这里补装）：

```bash
pip install -e ".[server,langfuse]"
```

**3.2 配置平台环境变量**：若 `.env` 已随项目 / 压缩包带来（本迁移包默认带），**直接复用即可、无需 cp**；只在 `.env` 缺失时从示例复制再按需填写（`.env` 含登录态 / 密钥，勿提交 git；跨机器复用后建议核对/轮换，详见下方各项）。

```bash
[ -f .env ] || cp .env.example .env
```

- `MEDEVAL_*`（数据库 / 路径 / 并发 / 上传上限）：留空走默认本地 SQLite（库文件本机首启自动生成），无需登录即可本地用。可选 `MEDEVAL_MAX_UPLOAD_BYTES`（默认 5 MiB）限制 benchmark 单文件上传大小。
- **运行环境 `MEDEVAL_ENV`**：默认 `development`（本地开发）。部署生产时设为 `production`（或 `prod`）——此时若 `SESSION_SECRET` 仍为默认值，**后端启动会直接失败**（强校验）；同时会话 cookie 自动加 `Secure`（需 HTTPS）。开发/测试环境不受此限制。
- 飞书 SSO（`FEISHU_APP_ID` / `FEISHU_APP_SECRET` / `FEISHU_REDIRECT_URI` / `SESSION_SECRET` 等）：仅在需要登录态 + per-user 导出时填齐；**配齐后平台才强制登录**。生产环境 `MEDEVAL_ENV=production` 时必须配置**非默认**随机强 `SESSION_SECRET`。
- **Langfuse 全链路追踪（`LANGFUSE_HOST` / `LANGFUSE_PUBLIC_KEY` / `LANGFUSE_SECRET_KEY`）**：`config.yaml` 默认 `observability.langfuse.enabled=true`，凭据只从 `.env` 读。若 `.env` **未随包带来**，新电脑须重填这三个值（自托管填内网地址，或用 Langfuse Cloud 的 `https://cloud.langfuse.com` + 项目 API Keys）；若已随压缩包带来则直接复用并核对是否仍有效。不填则追踪自动 no-op、前端「追踪链路」入口隐藏，不报错。**三个易踩的坑**：① SDK 必须装进**实际跑 server 的解释器**（本仓库即 `.venv`，需 `langfuse` extra，见步骤 1 / 3.1）；② `.env` 改完必须**重启后端**才生效（仅启动时加载）；③ 只有**新评测**会被追踪，旧 run / 离线重判（零 bot 调用）不回填。
- benchmark 库与历史落在 `uploads/`、SQLite 库文件、`outputs/`：属数据，迁移时是否带过来按需决定，不影响平台能否启动。

**3.3 还原前端依赖**（`frontend/node_modules` 不跨机器拷，必须本机重建）：

```bash
cd frontend && npm install && cd ..     # 按 package-lock.json 还原；也可用 npm ci
```

> 启动脚本 `scripts/dev_platform.sh` / `serve_platform.sh` 已内置 `npm install`，用脚本启动时本步可省略；手动起前端或想先验证依赖时执行。

**3.4 启动**：

```bash
scripts/dev_platform.sh                 # 开发：后端 :8000 + 前端 :5173（/api 自动代理）
# 或生产式（构建前端后由 FastAPI 静态托管）：
scripts/serve_platform.sh --port 8000   # 已构建过可加 --skip-build

# 不用脚本时手动起（两个终端）：
#   .venv/bin/python -m uvicorn server.app:app --reload --port 8000
#   cd frontend && npm run dev
```

> 平台 SQLite 库（`medeval_platform.db`）首次启动由 `init_db()` 自动建表；不拷旧库即得空库，拷旧库则保留历史平台数据。

**验证**：

- 开发态：浏览器打开 `http://localhost:5173`，看板可加载。
- 生产态：浏览器打开 `http://localhost:8000`。
- 后端单测：`pytest tests/server`。

> 平台环境变量与登录/导出细节见 `server/README.md` 与 `.env.example`。

### 3.5 平台数据：数据库与评测产物（按需迁移 / 清理）

平台数据分三层，迁移时按需取舍（纯 CLI 评测可全跳过）：

| 数据 | 位置 | 内容 / 依赖 |
|------|------|------------|
| 平台数据库 | `medeval_platform.db`（默认 SQLite，单文件） | benchmark 库 / 评测 run / 用例结果 / Pairwise 对比 / 判分模型配置 / 人工裁定 / 登录态 |
| 上传 benchmark | `uploads/benchmarks/<id>/` | 网页上传/派生的用例 YAML；**被 DB 的 `benchmark.storage_path` 绑定** |
| 评测产物 | `outputs/<run>/` | `report.json`（已落 DB）/ `traces.jsonl.gz` / `transcripts.xlsx`；traces 仅重判/续跑/追踪链路/导出时才用 |

- **迁移数据库 = 拷一个文件**：把 `medeval_platform.db` 拷到新电脑项目根同名位置即可，**无需 dump/restore**。不拷则首次启动 `init_db()` 自动建空库（内置乳腺癌 benchmark 启动时自动注册）。
- ⚠️ **SQLite 删行不缩容**：从网页删除评测/benchmark 后，`.db` 文件大小**不会自动变小**（仅把页标记为空闲）。迁移前想瘦身先 `VACUUM`：

  ```bash
  sqlite3 medeval_platform.db "VACUUM;"   # 真正回收空间；非破坏性，只压缩
  ```

- ⚠️ **`uploads/` 与 DB 绑定**：**勿单独删 `uploads/` 却保留 DB**——上传/派生的 benchmark 会失效（内置 benchmark 指向仓库内 `cases/`，不受影响）。要清就连同对应 DB 记录一起清（最稳是走网页"删除 benchmark"）。
- **前台删除已联动清理**：网页删 run / benchmark 会级联清 DB + 对应 `outputs/` / `uploads/` 目录，但可能残留空的 `uploads/benchmarks/_staging` 或个别孤儿 `outputs/<run>` 目录（库里已无对应 run），可直接 `rm -rf` 清掉，不影响平台。
- **Postgres**（仅当用 `MEDEVAL_DATABASE_URL` 切到 PG 时）才需 `pg_dump` / `pg_restore`；默认 SQLite 无此步。

> 想"只带代码、平台从零开始"：迁移时**不拷** `medeval_platform.db` / `outputs/` / `uploads/` 即可（附录 A 的 rsync 加上对应 `--exclude`）。想保留已配好的判分模型/历史：拷（建议先 `VACUUM`）数据库，并连同 `uploads/` 一起带过去。

---

## 4. ⭐ 推荐：安装 graphify（代码知识图谱）

本项目 `graphify-out/` 已随代码拷贝；要继续「改码后刷新图谱」需装 graphify 二进制。

```bash
pipx install graphifyy                 # 包名 graphifyy，命令名 graphify（旧机版本 0.8.26）
graphify --version                     # 验证
```

**验证**（项目根目录）：

```bash
graphify query "项目结构"               # 能基于 graphify-out/graph.json 返回子图
```

> 按项目规则：每次任务启动 & 结束、改码后都应 `graphify update .` 刷新图谱。

---

## 5. 迁移所有 skill 与 rule（项目级 + 全局级）

skill / rule 分**项目级**（随项目走）和**全局级**（装在用户目录，与项目无关）。

### 5.1 项目级（✅ 已随项目拷贝，无需额外操作）

打开项目即生效，都在 `.cursor/` 下：

- `.cursor/rules/`：`workflow-lock.mdc`、`graphify.mdc`、`frontend-workflow.mdc`、`respond-in-chinese.mdc`
- `.cursor/hooks/` + `.cursor/hooks.json`：工作流锁钩子
- `.cursor/commands/`：`opsx-*` 命令
- `.cursor/skills/`：`openspec-*` 工作流 skill、`impeccable`（前端设计，脚本在 `impeccable/scripts/`）
- 以及根目录的 `AGENTS.md`（项目知识库 / agent 约定）

### 5.2 全局 skill —— 联网重装（默认）

> 全局 skill 与 `medeval` 运行**无关**，只为复刻同样的 AI 辅助环境。它们装在**用户目录**（`~/.agents/skills`、`~/.claude/skills`），**不随项目 / 本压缩包走**，需在新机单独还原。

用安装器 `npx skills` 重装（联网、拿最新版；`-g` 全局、`-y` 跳过确认）：

```bash
npx skills add open.feishu.cn -g -y     # 飞书全家桶 lark-*（发布飞书报告才需要）
npx skills add vercel-labs/skills -g -y # find-skills（skill 安装器本体）
npx skills add jackwener/opencli -g -y  # opencli 三件套（本项目用不到，可跳过）
npx skills add anthropics/skills -g -y  # skill-creator（可跳过）
```

- **graphify skill 不在 npx 源里**：从旧机把整个 `~/.claude/skills/graphify` 目录拷到新机同路径即可。

**验证**：`npx skills list` 或 `ls ~/.agents/skills` 应能看到已装 skill。底层 CLI（`lark-cli`、`graphify` 二进制）仍需按步骤 4/6 单独安装。

> **想要离线 / 与旧机逐字节一致的还原**：在旧机把用户目录 `~/.agents/skills`、`~/.claude/skills`、`~/.claude/CLAUDE.md` 一并拷到新机同路径（`~/.claude/skills` 内若含软链需一并重建）。**本压缩包默认不含这些用户目录文件**（它们在项目目录之外）。

### 5.3 全局 rule

- 可移植的全局 rule 只有 `~/.claude/CLAUDE.md`（graphify 触发约定）——从旧机拷到新机 `~/.claude/CLAUDE.md` 同路径即可（不在项目内，本压缩包不含）。
- **Cursor 用户级 rule** 存在 Cursor App 内部（非文件），无法拷贝；如有自定义用户 rule，请在新电脑的 Cursor「Settings → Rules」里重新添加。

---

## 6. 按需：安装 lark-cli（发布飞书报告 / lark-* skill 的底层依赖）

lark-* skill 仅靠 SKILL.md 文件还不能用，必须有底层 CLI。

```bash
npm install -g @larksuite/cli          # 命令名 lark-cli（旧机版本 1.0.44）
lark-cli --version                     # 验证
lark-cli auth login                    # 重新登录飞书（登录态现登现用，不要跨机器拷）
```

**按需：从飞书电子表格导入 benchmark YAML**（与步骤 6 共用 `lark-cli`）：

```bash
medeval import-feishu --help           # 表头与产出见 cases/README.md
```

---

## 7. 按需：恢复认证 / 网关配置文件

这些是机器级密钥/配置，从旧电脑拷到新电脑**同样路径**（仅在使用对应能力时需要）：

```text
~/.llmbox/claude_byted_token.sh        # llmbox.json 的 apiKeyHelper 指向它
~/.claude/llmbox.json
~/.claude/settings.json
~/.claude/settings.local.json
```

---

## 验证清单（最终自检）

| 命令 | 期望结果 | 关联步骤 |
|------|---------|---------|
| `medeval --help` | 打印 CLI 帮助 | 1 |
| `medeval validate` | 用例库校验通过 | 1 |
| `pytest -m golden` | 黄金集回归通过 | 1 |
| `medeval run --config config.yaml --limit 1 --dry-run` | 正常生成 dry-run | 2 |
| `scripts/dev_platform.sh` + 打开 `http://localhost:5173` | 平台看板可加载 | 3 |
| `cd frontend && npm run test` | Vitest 单测通过 | 3 |
| `pytest tests/server` | 平台后端单测通过 | 3 |
| `graphify --version` | 输出 0.8.x | 4 |
| `graphify query "项目结构"` | 返回子图 | 4 |
| `npx skills list` | 列出已装 skill | 5 |
| `lark-cli --version` | 输出 1.0.x | 6 |

---

## 按目标取舍（最小执行集）

| 目标 | 需要执行的步骤 |
|------|--------------|
| 只想**跑评测（CLI）** | 0 → 1 → 2 |
| 跑**评测平台（Web）** | 0 → 1 → 2 → 3 |
| **本地 Docker Compose**（跨平台一致，Mac 可用 Colima） | 0 → 1 → 2 → 8.3（`docker compose up`）；飞书回调用 `:8000`，见 8.2 旁注 |
| **云主机 Docker 生产部署（公网 HTTPS）** | 8（Git 推送 → 云主机 Docker → Nginx/HTTPS） |
| 跑评测 + **代码图谱工作流** | 0 → 1 → 2 →（按需 3）→ 4 |
| 以上 + **发布飞书报告** | 再加 5（lark 那行）→ 6 →（7 按需） |
| 完整复刻全部 AI 辅助环境 | 全部步骤 0 → 7 |

> 注：`outputs/`（历史评测结果）、`uploads/`（benchmark 库）、平台 SQLite 库是否保留随意，不影响运行；每次 `medeval run` 落独立目录、不覆盖、会累积，需自行清理。

---

## 附录 A：从旧电脑拷贝项目（rsync）

在**旧电脑**执行，把项目拷到目标位置（如 U 盘 / 待传目录）。务必排除可重建产物——尤其 `frontend/node_modules`（约 230M）和 `.venv`，否则又大又慢：

```bash
rsync -av --delete \
  --exclude='.venv' \
  --exclude='node_modules' \
  --exclude='__pycache__' \
  --exclude='*.egg-info' \
  --exclude='.pytest_cache' \
  --exclude='.DS_Store' \
  --exclude='graphify-out/cache' \
  --exclude='graphify-out/20*' \
  /Users/bytedance/Documents/medical-chatbot-eval/ \
  <目标路径>/medical-chatbot-eval/
```

- `--delete`：让目标与源**完全一致**（删掉源已不存在的旧文件）。首次拷贝到空目录可省略。
- 后两条排除 `graphify-out` 的历史日期快照与 cache（均可重建，新机 `graphify update .` 重算）；保留当前 `graph.json` + wiki + 报告。排除以上各项后约 **30M 量级**（不压缩）、秒级完成。
- 数据类目录 `outputs/` / `uploads/` / `medeval_platform.db` 默认会被拷贝；不想带历史数据可再加 `--exclude='outputs' --exclude='uploads' --exclude='medeval_platform.db'`。

## 附录 B：新电脑「还原命令」速查

把项目拷到（或解压到）新电脑后，按序执行即可还原全部可重建产物。下面只重建被排除的产物（`.venv` / `node_modules` / 缓存 / graphify 历史快照），**源码、`config.yaml`、`cases/` 等已随包带过来，无需重建**。

```bash
# 0) 若是压缩包：先解压并进入项目根
tar xzf medical-chatbot-eval-migration-*.tar.gz   # 解出 medical-chatbot-eval/
cd medical-chatbot-eval

# 1) Python 环境（替代被排除的 .venv）
python3 -m venv .venv
source .venv/bin/activate                         # Windows: .venv\Scripts\activate
pip install -e ".[dev,llm-openai,server,langfuse]" # CLI + 测试 + LLM judge + 平台后端 + Langfuse 追踪

# 2) 前端依赖（替代被排除的 frontend/node_modules；纯 CLI 可跳过）
cd frontend && npm install && cd ..

# 3) 验证 CLI（不打真实 API）
medeval --help && medeval validate && medeval list-cases
pytest -m golden                                   # HardGate 黄金集回归应通过

# 4) 平台环境变量 .env（按需，纯 CLI 可跳过）
#  · 若 .env 已随包带来（本迁移包默认带）：无需 cp，直接复用；建议核对/轮换密钥，
#    并确认 Langfuse（LANGFUSE_*）/ 飞书 SSO / SESSION_SECRET 在新机仍有效。
#  · 若 .env 未带（迁移时排除了）：cp .env.example .env 再按需填密钥。改完 .env 必须重启后端才生效。
#  · 生产部署：MEDEVAL_ENV=production 且 SESSION_SECRET 必须为非默认值，否则后端拒绝启动。
[ -f .env ] || cp .env.example .env

# 5) 平台数据库 medeval_platform.db
#  · 若 .db 已随包带来（本迁移包默认带）：直接复用，保留全部历史平台数据，无需操作。
#  · 若 .db 未带：首次启动 init_db() 自动建空库（内置乳腺癌 benchmark 自动注册）；
#    如需把 outputs/ 历史评测导入空库：.venv/bin/python -m server.import_history outputs

# 6) 起平台（可选）
scripts/dev_platform.sh                            # 开发：后端 :8000 + 前端 :5173
# scripts/serve_platform.sh --port 8000            # 生产：构建前端后由 FastAPI 静态托管
```

> graphify / lark-cli / 全局 skill 的还原见步骤 4–7。`graphify-out/` 的历史日期快照与 cache 属可重建产物（迁移时通常排除），新机首次 `graphify update .` 会按需重算（AST-only、零 API 成本）。
> 密钥说明：`config.yaml` 已内联兜底 key 故 CLI 开箱即跑；`config.yaml` 引用的环境变量（`DOUBAO_API_KEY` / `AIDP_API_KEY` 等）与飞书凭证若用环境变量方式则需在新机另行 `export`（见步骤 2）。

---

## 8. 按需：生产部署（Git → 云主机 → 公网 HTTPS）

> 适用：把项目推到 Git，在云主机上用 **Docker Compose** 部署，并通过域名 **公网 HTTPS** 访问 MME 评测平台。
>
> **与本地开发的关系**：本节只增加 `Dockerfile` / `docker-compose.yml` 等部署文件；**不影响**步骤 3 的 `scripts/dev_platform.sh` / `scripts/serve_platform.sh` 本地启动。不跑 Docker 时与迁移前完全一致。
>
> **架构约束**：平台 `JobRunner` 为进程内 asyncio 调度，Compose 请保持 **`app` 单实例**；水平多副本需外部队列（当前未实现）。

### 8.1 本地：推送到 Git 之前

**切勿提交**（`.gitignore` 已覆盖，提交前用 `git status` 再确认）：

| 路径 | 原因 |
|------|------|
| `.env` | `SESSION_SECRET`、飞书 Secret |
| `.venv/`、`frontend/node_modules/`、`frontend/dist/` | 本机构建产物 |
| `outputs/`、`uploads/`、`*.db` | 评测数据 |
| 含明文密钥的 `config.yaml` | 泄露风险（见下） |

⚠️ **`config.yaml` 密钥**：当前文件可能内联了 `api_key` 兜底。推 Git **前**建议清空内联 `api_key`、只保留 `api_key_env`，密钥放在云主机 `.env` 或环境变量；或把生产用 `config.yaml` 仅放在服务器挂载、不进仓库。

```bash
# 提交前自查
grep -n 'api_key:' config.yaml    # 不应出现真实 key
git status                        # 不应出现 .env / outputs / uploads / *.db

# 首次推送到远程（仓库已 git init、本地已有 commit 时）
git remote add origin https://github.com/<user>/medical-chatbot-eval.git   # 仅首次
git push -u origin main

# 若远程仓库为空、本地尚无 commit（少见）：
# git add . && git commit -m "Initial commit" && git push -u origin main
```

### 8.2 云主机：准备环境

推荐（单机够用）：

| 项 | 建议 |
|----|------|
| 系统 | Ubuntu 22.04 / 24.04 |
| 规格 | 2 核 4G 起 |
| 磁盘 | ≥ 50GB（`outputs/` 会持续增长） |
| 安全组 | 开放 **22**（SSH）、**80**（HTTP）、**443**（HTTPS）；**不要**把 **8000** 直接暴露公网 |

安装 Docker（SSH 登录云主机后）：

```bash
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER
# 重新登录 SSH 使 docker 组生效
docker --version && docker compose version
```

> **Mac 本机无 Docker Desktop 时**：可用 Homebrew 安装 `docker` + `colima`（`brew install docker colima docker-compose` → `colima start`），再执行下文 `docker compose up`。飞书 SSO 用 Docker 单端口 `8000` 时，开发者后台须登记 `http://localhost:8000/api/auth/feishu/callback`（与 `dev_platform.sh` 的 `:5173` 回调可并存）。

### 8.3 云主机：拉代码、配置、启动

```bash
git clone https://github.com/<user>/medical-chatbot-eval.git
cd medical-chatbot-eval

cp .env.docker.example .env
nano .env          # 见 8.4 必改项
nano config.yaml   # 被测 bot / judge 真实配置（密钥优先走 env）
```

启动：

```bash
docker compose up -d --build
docker compose ps
docker compose logs -f app
```

**验证**（在云主机本机）：

```bash
curl -s http://127.0.0.1:8000/api/health   # 期望 {"status":"ok"}
```

此时仅本机 `:8000` 可访问；公网需 8.5 配置域名与 HTTPS。

**持久化**：数据在 Docker volume 中，`docker compose down` **不会**删除 volume：

| Volume | 内容 |
|--------|------|
| `mme-data` | `outputs/`、`uploads/benchmarks/` |
| `pgdata` | Postgres 数据 |

默认挂载宿主机 `./config.yaml` → 容器 `/app/config.yaml`（只读）；可设环境变量 `MEDEVAL_CONFIG_HOST_PATH` 指向其他路径。

### 8.4 `.env` 生产必改项

```bash
# 生成强随机 SESSION_SECRET
openssl rand -hex 32
```

| 变量 | 说明 |
|------|------|
| `MEDEVAL_ENV=production` | 启用生产校验；默认 `SESSION_SECRET` 会拒绝启动 |
| `SESSION_SECRET` | **必须**改为 `openssl rand -hex 32` 生成的值 |
| `FRONTEND_URL` | 公网访问根 URL，如 `https://eval.example.com` |
| `FEISHU_REDIRECT_URI` | 与飞书后台一致，如 `https://eval.example.com/api/auth/feishu/callback` |
| `FEISHU_APP_ID` / `FEISHU_APP_SECRET` | 需要登录 + per-user 导出时必填 |
| `POSTGRES_PASSWORD` | 改掉默认值，并与 `MEDEVAL_DATABASE_URL` 中密码一致 |

内网可信、**不需要登录**时：`FEISHU_APP_ID` 留空即可（dev 兜底放行，仅适合内网）。

### 8.5 公网访问：域名 + Nginx + HTTPS

`MEDEVAL_ENV=production` 时会话 cookie 需 **Secure**，飞书 OAuth 也要求回调 URL 与域名一致，**必须 HTTPS**。

**1）DNS**：添加 A 记录 `eval.example.com` → 云主机公网 IP。

**2）Nginx（SPA `try_files` + API 反代）**

仓库提供模板 `deploy/nginx/mme.conf`（`location /` 使用 `try_files $uri $uri/ /index.html;`，与容器内 `server/spa_static.py` **双保险**）。完整步骤见 [`deploy/nginx/README.md`](deploy/nginx/README.md)。

```bash
sudo apt install -y nginx certbot python3-certbot-nginx

# 先启动 Docker app（:8000）
docker compose up -d --build

# 把容器内 frontend/dist 同步到 Nginx 可读目录
sudo scripts/sync_nginx_static.sh /var/www/mme/frontend/dist

# 安装站点（记得改 server_name）
sudo cp deploy/nginx/mme.conf /etc/nginx/sites-available/mme
sudo nano /etc/nginx/sites-available/mme   # eval.example.com → 你的域名

sudo ln -sf /etc/nginx/sites-available/mme /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx

sudo certbot --nginx -d eval.example.com
```

每次 `docker compose up -d --build` **更新前端**后，重新执行 `sync_nginx_static.sh`，否则 Nginx 仍服务旧静态资源。

**3）飞书开发者后台**：重定向 URL = `.env` 中 `FEISHU_REDIRECT_URI`（完全一致）。

浏览器访问：**https://eval.example.com**（`/runs` 可直接打开或刷新）。

### 8.6 架构示意

```text
用户浏览器
    ↓ HTTPS :443
Nginx（TLS + try_files SPA + /api 反代）
    ├─ /、/runs、/assets → 宿主机 /var/www/mme/frontend/dist（sync_nginx_static.sh）
    └─ /api/* → HTTP 127.0.0.1:8000（不暴露公网）
docker compose
    ├── app   FastAPI（API + SPA 回退双保险）
    └── db    Postgres 16
         volumes: mme-data（outputs/uploads）、pgdata（DB）
```

### 8.7 日常运维

```bash
# 更新代码后重新部署
git pull
docker compose up -d --build

docker compose logs -f app
docker compose down              # 停止容器；volume 数据保留

# Postgres 备份示例
docker compose exec db pg_dump -U medeval medeval > backup-$(date +%F).sql
```

### 8.8 生产部署检查清单

| 检查项 | 说明 |
|--------|------|
| Git 无 `.env` / 明文 API Key / `outputs/` | `git status` + `grep api_key config.yaml` |
| `SESSION_SECRET` 已换强随机值 | `MEDEVAL_ENV=production` 下必过启动校验 |
| `FRONTEND_URL`、飞书回调为 **https + 真实域名** | 与飞书后台一致 |
| Nginx + 证书已生效 | 浏览器地址栏有锁；配置见 `deploy/nginx/mme.conf` |
| Nginx 已同步 `frontend/dist` | `sudo scripts/sync_nginx_static.sh`（前端更新后重做） |
| `config.yaml` 中被测 bot 从云主机可达 | 评测任务能调通 adapter |
| 安全组仅 22/80/443 | 8000 只监听本机，不经公网直连 |
| `app` 仅 1 副本 | 进程内 JobRunner 不支持多实例抢任务 |

### 8.9 与「按目标取舍」对照

| 目标 | 步骤 |
|------|------|
| 本地开发 Web 平台 | 0 → 1 → 2 → 3（`dev_platform.sh`） |
| **云主机 Docker 生产部署** | 8.1 → 8.2 → 8.3 → 8.4 → 8.5 |
| 生产 + 保留历史平台数据 | 迁移时带上 `pgdata`/`mme-data` 或 Postgres dump + `uploads/`/`outputs/`（见 3.5） |

> 部署细节与 Compose 环境变量说明亦见 `server/README.md`（Docker Compose 章节）、仓库根 `docker-compose.yml`、`.env.docker.example`。
