#!/bin/bash
# workflow-lock 强制检查（配套 .cursor/rules/workflow-lock.mdc）。
#
# 在 preToolUse（编辑类工具）与 beforeShellExecution（写文件式 shell）阶段，拦截
# "改动受治理代码面 但 openspec/changes/ 下无进行中变更" 的情况，返回 permission=ask
# 提醒先按固定开发流程创建 OpenSpec change。fail-open：任何异常一律放行，绝不卡住工作。
#
# 判定要点：
#   - 受治理代码面 = medeval/ | tests/ | cases/ 下的 .py/.yaml，或根目录 config.yaml。
#   - 编辑类（preToolUse）：只从 path/file_path/target_file 等字段取路径来判定（不扫正文，避免
#     "文档里提到代码路径"被误判）；覆盖 Write/StrReplace/EditNotebook/Delete。
#   - shell 类（beforeShellExecution）：仅当命令含写文件信号（sed -i / tee / dd / 重定向 >）
#     且目标落在代码面时才介入；pytest / git / ls 等只读命令放行。
#   - 进行中变更 = openspec/changes/ 下任一非 archive、且同时含 tasks.md 与 proposal.md 的目录。

set -u

allow() { printf '{"permission":"allow"}\n'; exit 0; }
ask() {
  cat <<'JSON'
{
  "permission": "ask",
  "user_message": "⚠️ workflow-lock：正在改动受治理代码面，但 openspec/changes/ 下没有进行中的变更。按固定开发流程应先创建 OpenSpec change（刷新图谱 → 澄清 → 建 change → TDD）再编码。确认继续吗？",
  "agent_message": "workflow-lock hook 命中：检测到对受治理代码面（medeval/ tests/ cases/ config.yaml）的改动，但没有进行中的 OpenSpec change（需同时含 tasks.md 与 proposal.md）。除非属于规则 §4 的豁免情形，否则请先停下、按固定开发流程创建 openspec/changes/<name>/ 并刷新 graphify，再继续。"
}
JSON
  exit 0
}

# 字符串是否触及"受治理代码面"
touches_code() {
  printf '%s' "$1" | grep -Eq '(^|[^A-Za-z0-9_])(medeval|tests|cases)/[A-Za-z0-9_./-]*\.(py|ya?ml)([^A-Za-z0-9]|$)' && return 0
  printf '%s' "$1" | grep -Eq '(^|[^A-Za-z0-9_])config\.yaml([^A-Za-z0-9]|$)' && return 0
  return 1
}

# shell 命令是否"写入"受治理代码面（重定向/ tee / sed -i / dd 的目标是代码文件）。
# 关键：只看"写操作的目标"，不把 `--config config.yaml`、`pytest medeval/x.py`、
# `| tee /tmp/log` 这类只读参数 / 写非代码目标误判为改代码。
shell_writes_code() {
  local s="$1"
  # 重定向 / tee 的目标落在代码面
  printf '%s' "$s" | grep -Eq '(>>?|\btee\b)[[:space:]]*"?(\./)?(medeval|tests|cases)/[A-Za-z0-9_./-]*\.(py|ya?ml)' && return 0
  printf '%s' "$s" | grep -Eq '(>>?|\btee\b)[[:space:]]*"?(\./)?config\.yaml' && return 0
  # sed -i / 原地编辑代码文件
  printf '%s' "$s" | grep -Eq 'sed[[:space:]]+(-i|--in-place)[^|<>]*(medeval|tests|cases)/[A-Za-z0-9_./-]*\.(py|ya?ml)' && return 0
  printf '%s' "$s" | grep -Eq 'sed[[:space:]]+(-i|--in-place)[^|<>]*config\.yaml' && return 0
  return 1
}

# 是否存在"进行中"的 OpenSpec change（含 tasks.md 且含 proposal.md）
has_active_change() {
  local cd="$(pwd)/openspec/changes"
  [ -d "$cd" ] || return 1
  local d
  while IFS= read -r d; do
    [ -n "$d" ] || continue
    if [ -f "$d/tasks.md" ] && [ -f "$d/proposal.md" ]; then return 0; fi
  done < <(find "$cd" -mindepth 1 -maxdepth 1 -type d ! -name archive 2>/dev/null)
  return 1
}

input="$(cat 2>/dev/null)" || allow
[ -n "$input" ] || allow

# ---- 分支 1：shell 命令（beforeShellExecution）----
if printf '%s' "$input" | grep -Eq '"command"[[:space:]]*:'; then
  # 只在"写操作的目标是代码文件"时介入；只读命令（含 --config config.yaml、
  # pytest medeval/x.py、| tee /tmp/log 等）一律放行。
  shell_writes_code "$input" || allow
  has_active_change && allow
  ask
fi

# ---- 分支 2：编辑类工具（preToolUse）----
# A：只从路径字段取值，避免扫到正文造成误报
path="$(printf '%s' "$input" \
  | grep -oE '"(path|file_path|target_file|filePath|targetFile|target_notebook|file)"[[:space:]]*:[[:space:]]*"[^"]+"' \
  | head -1 | sed -E 's/.*:[[:space:]]*"([^"]+)"/\1/')"

[ -n "$path" ] || allow
touches_code "$path" || allow

has_active_change && allow
ask
