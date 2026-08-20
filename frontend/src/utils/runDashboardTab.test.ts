import { describe, expect, it } from "vitest";
import {
  runDashboardTabFromSearch,
  withRunDashboardTab,
} from "./runDashboardTab";

describe("runDashboardTab", () => {
  it("restores only supported tabs from the URL", () => {
    expect(runDashboardTabFromSearch("?tab=attribution")).toBe("attribution");
    expect(runDashboardTabFromSearch("?tab=detail")).toBe("detail");
    expect(runDashboardTabFromSearch("?tab=unknown")).toBeNull();
    expect(runDashboardTabFromSearch("")).toBeNull();
  });

  it("updates the active tab without discarding other URL parameters", () => {
    expect(withRunDashboardTab("?baseline=12", "diff")).toBe("?baseline=12&tab=diff");
  });
});
