import assert from "node:assert/strict";
import { mkdirSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { tmpdir } from "node:os";
import { fileURLToPath } from "node:url";
import { test } from "node:test";
import {
  checkNoScatteredHex,
  checkPagesLayer,
  checkTokenMirror,
  normalizeColor,
  parseTsRecord,
} from "./check-standards.mjs";

test("normalizeColor expands 3-digit hex", () => {
  assert.equal(normalizeColor("#abc"), "#aabbcc");
});

test("checkNoScatteredHex rejects hex in component files", () => {
  const dir = mkdtempSync(join(tmpdir(), "fe-check-"));
  const comp = join(dir, "src", "components");
  mkdirSync(comp, { recursive: true });
  writeFileSync(join(comp, "X.tsx"), 'const c = "#ff0000";');
  const errors = checkNoScatteredHex([join(comp, "X.tsx")], dir);
  assert.ok(errors.some((e) => e.includes("X.tsx")));
  rmSync(dir, { recursive: true, force: true });
});

test("checkPagesLayer rejects api.fetch in pages", () => {
  const dir = mkdtempSync(join(tmpdir(), "fe-pages-"));
  const pages = join(dir, "pages");
  mkdirSync(pages);
  writeFileSync(
    join(pages, "BadPage.tsx"),
    'import { api } from "../api";\nexport default () => { api.listRuns(); };'
  );
  const errors = checkPagesLayer(pages);
  assert.ok(errors.some((e) => e.includes("api.listRuns")));
  rmSync(dir, { recursive: true, force: true });
});

test("checkPagesLayer allows downloadBenchmarkUrl", () => {
  const dir = mkdtempSync(join(tmpdir(), "fe-pages-"));
  const pages = join(dir, "pages");
  mkdirSync(pages);
  writeFileSync(
    join(pages, "OkPage.tsx"),
    'import { api } from "../api";\nexport default () => <a href={api.downloadBenchmarkUrl(1)} />;'
  );
  const errors = checkPagesLayer(pages);
  assert.equal(errors.length, 0);
  rmSync(dir, { recursive: true, force: true });
});

test("parseTsRecord reads PROFILE_LABEL shape", () => {
  const src = `export const PROFILE_LABEL: Record<string, string> = {
  default: "默认（兜底）",
  agent: "Agent 问诊",
}`;
  const rec = parseTsRecord(src, "PROFILE_LABEL");
  assert.equal(rec.default, "默认（兜底）");
  assert.equal(rec.agent, "Agent 问诊");
});

test("checkTokenMirror passes on repo styles/theme", () => {
  const root = join(dirname(fileURLToPath(import.meta.url)), "..");
  const css = readFileSync(join(root, "src/styles.css"), "utf8");
  const theme = readFileSync(join(root, "src/theme.ts"), "utf8");
  const errors = checkTokenMirror(css, theme);
  assert.equal(errors.length, 0, errors.join("; "));
});
