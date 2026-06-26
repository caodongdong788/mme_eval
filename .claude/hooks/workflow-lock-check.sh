#!/bin/bash
# Claude Code 版 workflow-lock 强制检查（配套 .cursor/rules/workflow-lock.mdc）。
#
# 由 .cursor/hooks/workflow-lock-check.sh 改写而来，适配 Claude Code 的 PreToolUse
# hook 输入/输出协议。逻辑与 Cursor 版完全一致；fail-open：任何异常一律放行。
#
# 输入（stdin, JSON）：{ "tool_name": ..., "tool_input": {...}, "cwd": ..., ... }
# 输出（stdout, JSON）：
#   放行 -> {"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"allow"}}
#   拦截 -> 同结构，permissionDecision=ask + permissionDecisionReason
#
# 判定要点（与 Cursor 版一致）：
#   - 受治理代码面 = medeval/ | tests/ | cases/ 下的 .py/.yaml，或根目录 config.yaml。
#   - 编辑类（Edit/Write/MultiEdit/NotebookEdit）：只从 tool_input 的 file_path/notebook_path
#     取路径判定（不扫正文，避免"文档里提到代码路径"被误判）。
#   - Bash：仅当命令含写文件信号（sed -i / tee / dd / 重定向 >）且目标落在代码面才介入；
#     pytest / git / ls 等只读命令放行。
#   - 进行中变更 = openspec/changes/ 下任一非 archive、且同时含 tasks.md 与 proposal.md 的目录。

set -u

allow() {
  printf '{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"allow"}}\n'
  exit 0
}

ask() {
  cat <<'JSON'
{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"ask","permissionDecisionReason":"⚠️ workflow-lock 命中：检测到对受治理代码面（medeval/ tests/ cases/ config.yaml）的改动，但 openspec/changes/ 下没有进行中的 OpenSpec change（需同时含 tasks.md 与 proposal.md）。除非属于 workflow-lock.mdc §4 的豁免情形（如轻量 Bug），否则应先停下，按固定开发流程：刷新 graphify → 澄清 → 建 openspec/changes/<name>/ → TDD，再继续。确认继续吗？"}}
JSON
  exit 0
}

# 字符串是否触及"受治理代码面"
touches_code() {
  printf '%s' "$1" | grep -Eq '(^|[^A-Za-z0-9_])(medeval|tests|cases)/[A-Za-z0-9_./-]*\.(py|ya?ml)([^A-Za-z0-9]|$)' && return 0
  printf '%s' "$1" | grep -Eq '(^|[^A-Za-z0-9_])config\.yaml([^A-Za-z0-9]|$)' && return 0
  return 1
}

# shell 命令是否"写入"受治理代码面（重定向 / tee / sed -i / dd 的目标是代码文件）。
# 只看"写操作的目标"，不把 `--config config.yaml`、`pytest medeval/x.py`、
# `| tee /tmp/log` 这类只读参数 / 写非代码目标误判为改代码。
shell_writes_code() {
  local s="$1"
  printf '%s' "$s" | grep -Eq '(>>?|\btee\b)[[:space:]]*"?(\./)?(medeval|tests|cases)/[A-Za-z0-9_./-]*\.(py|ya?ml)' && return 0
  printf '%s' "$s" | grep -Eq '(>>?|\btee\b)[[:space:]]*"?(\./)?config\.yaml' && return 0
  printf '%s' "$s" | grep -Eq 'sed[[:space:]]+(-i|--in-place)[^|<>]*(medeval|tests|cases)/[A-Za-z0-9_./-]*\.(py|ya?ml)' && return 0
  printf '%s' "$s" | grep -Eq 'sed[[:space:]]+(-i|--in-place)[^|<>]*config\.yaml' && return 0
  return 1
}

# 是否存在"进行中"的 OpenSpec change（含 tasks.md 且含 proposal.md）
has_active_change() {
  local base="${1:-$(pwd)}/openspec/changes"
  [ -d "$base" ] || return 1
  local d
  while IFS= read -r d; do
    [ -n "$d" ] || continue
    if [ -f "$d/tasks.md" ] && [ -f "$d/proposal.md" ]; then return 0; fi
  done < <(find "$base" -mindepth 1 -maxdepth 1 -type d ! -name archive 2>/dev/null)
  return 1
}

input="$(cat 2>/dev/null)" || allow
[ -n "$input" ] || allow

# 用 python3 稳健解析 JSON（本仓库本就是 Python 项目）；不可用或失败一律 fail-open。
# 字段以 \x1f 分隔，command 放最后（可含换行）。
parsed="$(printf '%s' "$input" | python3 -c '
import sys, json
try:
    d = json.load(sys.stdin)
except Exception:
    sys.exit(0)
ti = d.get("tool_input") or {}
name = d.get("tool_name") or ""
path = ti.get("file_path") or ti.get("notebook_path") or ti.get("path") or ""
cwd = d.get("cwd") or ""
cmd = ti.get("command") or ""
sys.stdout.write("\x1f".join([name, path, cwd, cmd]))
' 2>/dev/null)" || allow

[ -n "$parsed" ] || allow

# 顺序参数展开提取 4 个字段（cmd 在最后，可含换行）
sep=$'\x1f'
tool_name="${parsed%%${sep}*}"; r="${parsed#*${sep}}"
path="${r%%${sep}*}";          r="${r#*${sep}}"
cwd="${r%%${sep}*}";           cmd="${r#*${sep}}"

case "$tool_name" in
  Bash)
    [ -n "$cmd" ] || allow
    shell_writes_code "$cmd" || allow
    has_active_change "$cwd" && allow
    ask
    ;;
  Edit|Write|MultiEdit|NotebookEdit)
    [ -n "$path" ] || allow
    touches_code "$path" || allow
    has_active_change "$cwd" && allow
    ask
    ;;
  *)
    allow
    ;;
esac
