import { describe, expect, it } from "vitest";
import type { RunSummary } from "../api/types";
import {
  mergeAttributionCategoryStats,
  selectLatestAttributedRunsByBenchmark,
} from "./latestAttributionCategoryStats";

function run(partial: Partial<RunSummary> & { id: number }): RunSummary {
  return {
    run_slug: `run_${partial.id}`,
    name: `run_${partial.id}`,
    status: "success",
    trigger_type: "manual",
    adapter_type: "openai_compat",
    total: 10,
    passed: 8,
    pass_rate: 0.8,
    medical_safety_failed: 0,
    n_runs: 1,
    error_msg: "",
    has_traces: true,
    pinned: false,
    evaluation_mode: "single_turn",
    ...partial,
  };
}

describe("latestAttributionCategoryStats", () => {
  it("keeps the latest attributed evaluation for each of the two benchmarks", () => {
    const selected = selectLatestAttributedRunsByBenchmark([
      run({ id: 1, benchmark_id: 10, cx_agent_optimization_count: 3, created_at: "2026-08-20T10:00:00Z" }),
      run({ id: 2, benchmark_id: 10, cx_agent_optimization_count: 4, created_at: "2026-08-21T10:00:00Z" }),
      run({ id: 3, benchmark_id: 20, cx_agent_optimization_count: 5, created_at: "2026-08-21T09:00:00Z" }),
      run({ id: 4, benchmark_id: 30, cx_agent_optimization_count: 6, created_at: "2026-08-19T10:00:00Z" }),
      run({ id: 5, benchmark_id: 30, cx_agent_optimization_count: null, created_at: "2026-08-22T10:00:00Z" }),
    ]);

    expect(selected.map((item) => item.id)).toEqual([2, 3]);
  });

  it("adds independently deduplicated benchmark category statistics", () => {
    expect(mergeAttributionCategoryStats([
      {
        attributed_case_count: 2,
        first_level: [{ key: "prompt", label: "提示词", case_count: 2 }],
        second_level: [{ key: "prompt:ask", label: "追问不足", case_count: 2, parent_key: "prompt", parent_label: "提示词" }],
      },
      {
        attributed_case_count: 3,
        first_level: [
          { key: "prompt", label: "提示词", case_count: 1 },
          { key: "rag", label: "RAG", case_count: 2 },
        ],
        second_level: [{ key: "prompt:ask", label: "追问不足", case_count: 1, parent_key: "prompt", parent_label: "提示词" }],
      },
    ])).toEqual({
      attributed_case_count: 5,
      first_level: [
        { key: "prompt", label: "提示词", case_count: 3 },
        { key: "rag", label: "RAG", case_count: 2 },
      ],
      second_level: [{ key: "prompt:ask", label: "追问不足", case_count: 3, parent_key: "prompt", parent_label: "提示词" }],
    });
  });
});
