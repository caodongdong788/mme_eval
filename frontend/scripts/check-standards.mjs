#!/usr/bin/env node
/**
 * 前端规范门禁（与 .cursor/rules/frontend-workflow.mdc 对齐）。
 * 用法：cd frontend && npm run check:standards
 */
import { readFileSync, readdirSync } from "node:fs";
import { join, relative } from "node:path";
import { fileURLToPath } from "node:url";

const FRONTEND_ROOT = join(fileURLToPath(import.meta.url), "..", "..");
const REPO_ROOT = join(FRONTEND_ROOT, "..");
const SRC = join(FRONTEND_ROOT, "src");

const HEX_RE = /#[0-9A-Fa-f]{3,8}\b/g;
const ALLOWED_HEX_REL = new Set(["src/styles.css", "src/theme.ts"]);
const BANNED_DEPS = [
  "@mui/material",
  "@mui/icons-material",
  "@chakra-ui/react",
  "tailwindcss",
  "styled-components",
  "@emotion/react",
  "@emotion/styled",
];
const PAGE_LINE_LIMIT = 300;
const PAGE_LAYER_ALLOWLIST = new Set(["LoginPage.tsx"]);
const PAGE_API_URL_METHOD_RE = /^(download\w*Url|\w+Url)$/;

const INK_TOKEN_PAIRS = [
  ["ink", "ink"],
  ["link", "link"],
  ["primary", "primary"],
  ["pass", "pass"],
  ["warn", "warn"],
  ["fail", "fail"],
  ["muted", "muted"],
];

const DASHBOARD_TOKEN_PAIRS = [
  ["runs-bg", "bg"],
  ["runs-card", "card"],
  ["runs-text", "text"],
  ["runs-text-secondary", "textSecondary"],
  ["runs-text-muted", "textMuted"],
  ["runs-border", "border"],
  ["runs-purple", "purple"],
  ["runs-purple-soft", "purpleSoft"],
  ["runs-purple-line", "purpleLine"],
  ["runs-teal", "teal"],
  ["runs-red", "red"],
];

export function normalizeColor(value) {
  if (!value) return "";
  let v = value.trim().toLowerCase();
  if (v.startsWith("#") && v.length === 4) {
    v = `#${v[1]}${v[1]}${v[2]}${v[2]}${v[3]}${v[3]}`;
  }
  return v;
}

export function walkFiles(dir, acc = []) {
  for (const name of readdirSync(dir, { withFileTypes: true })) {
    const p = join(dir, name.name);
    if (name.isDirectory()) {
      if (name.name === "node_modules" || name.name === "dist") continue;
      walkFiles(p, acc);
    } else if (/\.(tsx?|css)$/.test(name.name)) {
      acc.push(p);
    }
  }
  return acc;
}

export function extractCssVar(css, varName) {
  const re = new RegExp(`--${varName.replace(/-/g, "\\-")}:\\s*([^;\\n]+)`);
  const m = css.match(re);
  return m?.[1]?.trim() ?? null;
}

export function extractThemeTopLevel(theme, key) {
  const re = new RegExp(`^\\s*${key}:\\s*"([^"]+)"`, "m");
  const m = theme.match(re);
  return m?.[1] ?? null;
}

export function extractThemeDashboard(theme, key) {
  const block = theme.match(/dashboard:\s*\{([\s\S]*?)\n\s*\},/);
  if (!block) return null;
  const re = new RegExp(`\\b${key}:\\s*"([^"]+)"`);
  const m = block[1].match(re);
  return m?.[1] ?? null;
}

export function parseTsRecord(source, constName) {
  const m = source.match(
    new RegExp(
      `export\\s+const\\s+${constName}\\b[^=]*=\\s*\\{([\\s\\S]*?)\\n\\}`,
      "m"
    )
  );
  if (!m) return null;
  return parseRecordBody(m[1]);
}

export function parsePythonDict(source, constName) {
  const m = source.match(
    new RegExp(
      `^\\s*${constName}\\s*=\\s*\\{([\\s\\S]*?)\\n\\}`,
      "m"
    )
  );
  if (!m) return null;
  return parseRecordBody(m[1], true);
}

function parseRecordBody(body, pythonQuotedKeys = false) {
  const out = {};
  for (const line of body.split("\n")) {
    const trimmed = line.trim();
    if (!trimmed || trimmed.startsWith("#") || trimmed.startsWith("//")) continue;
    const kv = pythonQuotedKeys
      ? trimmed.match(/^["']([^"']+)["']\s*:\s*["']([^"']*)["'],?\s*$/)
      : trimmed.match(/^["']?([^"':\s]+)["']?\s*:\s*["']([^"']*)["'],?\s*$/);
    if (kv) out[kv[1]] = kv[2];
  }
  return out;
}

/** @deprecated use parseTsRecord / parsePythonDict */
export function parseStringRecord(source, constName) {
  return parseTsRecord(source, constName) ?? parsePythonDict(source, constName);
}

export function checkNoScatteredHex(
  files = walkFiles(SRC),
  frontendRoot = FRONTEND_ROOT
) {
  const errors = [];
  for (const file of files) {
    const rel = relative(frontendRoot, file).replace(/\\/g, "/");
    if (ALLOWED_HEX_REL.has(rel)) continue;
    const text = readFileSync(file, "utf8");
    const matches = text.match(HEX_RE);
    if (matches?.length) {
      errors.push(
        `${rel}: 禁止散落 hex（${[...new Set(matches)].join(", ")}）；请用 var(--*) 或 palette.*`
      );
    }
  }
  return errors;
}

export function checkBannedDeps(
  pkg = JSON.parse(readFileSync(join(FRONTEND_ROOT, "package.json"), "utf8"))
) {
  const errors = [];
  const all = { ...pkg.dependencies, ...pkg.devDependencies };
  for (const name of Object.keys(all)) {
    if (BANNED_DEPS.some((b) => name === b || name.startsWith(`${b}/`))) {
      errors.push(`package.json: 禁止依赖第二 UI 框架「${name}」`);
    }
  }
  return errors;
}

export function checkPagesLayer(pagesDir = join(SRC, "pages")) {
  const errors = [];
  for (const file of readdirSync(pagesDir).filter((f) => f.endsWith(".tsx"))) {
    if (PAGE_LAYER_ALLOWLIST.has(file)) continue;
    const rel = `src/pages/${file}`;
    const content = readFileSync(join(pagesDir, file), "utf8");
    const lines = content.split("\n").length;
    if (lines > PAGE_LINE_LIMIT) {
      errors.push(
        `${rel}: ${lines} 行超过 ${PAGE_LINE_LIMIT}，应拆到 hooks/ + components/`
      );
    }
    if (/\baxios\b/.test(content) || /\bfetch\s*\(/.test(content)) {
      errors.push(`${rel}: pages 禁止直接 axios/fetch，取数放 hooks/`);
    }
    for (const m of content.matchAll(/api\.(\w+)\s*\(/g)) {
      const method = m[1];
      if (!PAGE_API_URL_METHOD_RE.test(method)) {
        errors.push(
          `${rel}: pages 禁止 api.${method}()，仅允许 *Url 类辅助（如下载链接）`
        );
      }
    }
    if (/useEffect/.test(content) && /from\s+["'][^"']*\/api/.test(content)) {
      errors.push(
        `${rel}: pages 禁止 useEffect + api 导入并存，副作用放 hooks/（LoginPage 除外）`
      );
    }
  }
  return errors;
}

export function checkTokenMirror(
  css = readFileSync(join(SRC, "styles.css"), "utf8"),
  theme = readFileSync(join(SRC, "theme.ts"), "utf8")
) {
  const errors = [];
  for (const [cssKey, themeKey] of INK_TOKEN_PAIRS) {
    const cssVal = extractCssVar(css, cssKey);
    const themeVal = extractThemeTopLevel(theme, themeKey);
    if (!cssVal || !themeVal) {
      errors.push(`token 镜像缺失: --${cssKey} ↔ palette.${themeKey}`);
      continue;
    }
    if (normalizeColor(cssVal) !== normalizeColor(themeVal)) {
      errors.push(
        `token 漂移: --${cssKey}=${cssVal} ≠ palette.${themeKey}=${themeVal}`
      );
    }
  }
  for (const [cssKey, themeKey] of DASHBOARD_TOKEN_PAIRS) {
    const cssVal = extractCssVar(css, cssKey);
    const themeVal = extractThemeDashboard(theme, themeKey);
    if (!cssVal || !themeVal) {
      errors.push(
        `dashboard token 镜像缺失: --${cssKey} ↔ palette.dashboard.${themeKey}`
      );
      continue;
    }
    if (normalizeColor(cssVal) !== normalizeColor(themeVal)) {
      errors.push(
        `dashboard token 漂移: --${cssKey}=${cssVal} ≠ palette.dashboard.${themeKey}=${themeVal}`
      );
    }
  }
  return errors;
}

export function checkProfileLabelsSync(
  labelsTs = readFileSync(join(SRC, "labels.ts"), "utf8"),
  serverPy = readFileSync(
    join(REPO_ROOT, "server/services/platform_config.py"),
    "utf8"
  )
) {
  const errors = [];
  const fe = parseTsRecord(labelsTs, "PROFILE_LABEL");
  const be = parsePythonDict(serverPy, "PROFILE_LABELS_ZH");
  if (!fe || !be) {
    errors.push("无法解析 PROFILE_LABEL / PROFILE_LABELS_ZH 用于同步校验");
    return errors;
  }
  const keys = new Set([...Object.keys(fe), ...Object.keys(be)]);
  for (const k of [...keys].sort()) {
    if (!(k in fe)) {
      errors.push(`labels.ts PROFILE_LABEL 缺少 key「${k}」（后端已有）`);
    } else if (!(k in be)) {
      errors.push(
        `server PROFILE_LABELS_ZH 缺少 key「${k}」（前端 labels.ts 已有）`
      );
    } else if (fe[k] !== be[k]) {
      errors.push(
        `PROFILE 中文漂移 key=${k}: 前端「${fe[k]}」≠ 后端「${be[k]}」`
      );
    }
  }
  return errors;
}

export function runAllChecks() {
  return [
    ...checkNoScatteredHex(),
    ...checkBannedDeps(),
    ...checkPagesLayer(),
    ...checkTokenMirror(),
    ...checkProfileLabelsSync(),
  ];
}

function main() {
  const errors = runAllChecks();
  if (errors.length) {
    console.error("frontend check:standards FAILED\n");
    for (const e of errors) console.error(`  ✗ ${e}`);
    console.error(
      "\n规范见 .cursor/rules/frontend-workflow.mdc · 设计见 DESIGN.md"
    );
    process.exit(1);
  }
  console.log("frontend check:standards OK");
}

import { pathToFileURL } from "node:url";

const isMain =
  process.argv[1] &&
  import.meta.url === pathToFileURL(process.argv[1]).href;

if (isMain) {
  main();
}
