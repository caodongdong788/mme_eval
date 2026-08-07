import { describe, expect, it } from "vitest";
import { RunDetail } from "../api/index";
import { renderWithProviders } from "../test/renderWithProviders";
import { RunOverviewMetricsPanel } from "./RunOverviewMetricsPanel";

const baseRun = {
  latency_summary: {
    count: 3,
    avg_ms: 12_600,
    median_ms: 12_200,
    p90_ms: 14_300,
  },
  ttft_summary: {
    count: 3,
    avg_ms: 1_280,
  },
  token_summary: {},
  grading: {},
} as unknown as RunDetail;

describe("RunOverviewMetricsPanel", () => {
  it("renders the single-run TTFT metric from ttft_summary", () => {
    const { getByText } = renderWithProviders(<RunOverviewMetricsPanel run={baseRun} />);

    expect(getByText("平均首 Token 耗时（TTFT）")).toBeInTheDocument();
    expect(getByText("1,280")).toBeInTheDocument();
  });

  it("keeps the performance card available when only TTFT is present", () => {
    const run = {
      ...baseRun,
      latency_summary: {},
      ttft_summary: { count: 1, avg_ms: 320 },
    } as RunDetail;
    const { getByText, container } = renderWithProviders(<RunOverviewMetricsPanel run={run} />);

    expect(getByText("320")).toBeInTheDocument();
    expect(container.querySelector(".runs-chart-card")).not.toHaveTextContent(
      "本次评测无相关数据",
    );
  });
});
