import assert from "node:assert/strict";
import { mkdirSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { tmpdir } from "node:os";
import { fileURLToPath } from "node:url";
import { test } from "node:test";
import {
  checkNoScatteredHex,
  checkDimensionLabelsSync,
  checkPagesLayer,
  checkTokenMirror,
  normalizeColor,
  parsePythonEnumDict,
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

test("parseTsRecord reads DIM_LABEL shape", () => {
  const src = `export const DIM_LABEL: Record<string, string> = {
  medical_safety: "医学安全性",
  empathy: "被理解与共情",
}`;
  const rec = parseTsRecord(src, "DIM_LABEL");
  assert.equal(rec.medical_safety, "医学安全性");
  assert.equal(rec.empathy, "被理解与共情");
});

test("parsePythonEnumDict reads enum-keyed label mapping", () => {
  const src = `DIMENSION_LABELS: dict[EvaluationDimension, str] = {
    EvaluationDimension.medical_safety: "医学安全性",
    EvaluationDimension.empathy: "被理解与共情",
}`;
  const rec = parsePythonEnumDict(src, "DIMENSION_LABELS", "EvaluationDimension");
  assert.equal(rec.medical_safety, "医学安全性");
  assert.equal(rec.empathy, "被理解与共情");
});

test("dimension labels stay synchronized across frontend and backend", () => {
  const root = join(dirname(fileURLToPath(import.meta.url)), "..", "..");
  const labels = readFileSync(join(root, "frontend/src/labels.ts"), "utf8");
  const evaluation = readFileSync(join(root, "medeval/evaluation.py"), "utf8");
  const errors = checkDimensionLabelsSync(labels, evaluation);
  assert.equal(errors.length, 0, errors.join("; "));
});

test("checkTokenMirror passes on repo styles/theme", () => {
  const root = join(dirname(fileURLToPath(import.meta.url)), "..");
  const css = readFileSync(join(root, "src/styles.css"), "utf8");
  const theme = readFileSync(join(root, "src/theme.ts"), "utf8");
  const errors = checkTokenMirror(css, theme);
  assert.equal(errors.length, 0, errors.join("; "));
});
