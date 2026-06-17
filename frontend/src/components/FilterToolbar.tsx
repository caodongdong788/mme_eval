import { Dispatch, SetStateAction } from "react";
import { Select, Switch } from "antd";
import { FilterOutlined } from "@ant-design/icons";
import { DashTableLink } from "./DashTableActions";

export type CaseFilters = Record<string, string | undefined>;

export interface FilterToolbarProps {
  filters: CaseFilters;
  setFilters: Dispatch<SetStateAction<CaseFilters>>;
  reviewFilter?: string;
  setReviewFilter: (value: string | undefined) => void;
  onlyPending: boolean;
  setOnlyPending: (checked: boolean) => void;
  queueIds: Set<string>;
  hasActiveFilters: boolean;
  resetFilters: () => void;
}

export function FilterToolbar({
  filters,
  setFilters,
  reviewFilter,
  setReviewFilter,
  onlyPending,
  setOnlyPending,
  queueIds,
  hasActiveFilters,
  resetFilters,
}: FilterToolbarProps) {
  return (
    <div className="case-toolbar dash-filter-bar">
      <span className="case-toolbar__lead">
        <FilterOutlined />
        筛选
      </span>
      <Select
        allowClear
        placeholder="人审结果"
        value={reviewFilter}
        onChange={(v) => setReviewFilter(v)}
        options={[
          { value: "agree", label: "同意" },
          { value: "override", label: "推翻" },
          { value: "none", label: "未审" },
        ]}
      />
      <Select
        allowClear
        placeholder="上线判定"
        value={filters.release_passed}
        onChange={(v) => setFilters((f) => ({ ...f, release_passed: v }))}
        options={[
          { value: "true", label: "通过" },
          { value: "false", label: "失败" },
        ]}
      />
      <Select
        allowClear
        placeholder="Level"
        value={filters.level}
        onChange={(v) => setFilters((f) => ({ ...f, level: v }))}
        options={["L1", "L2", "L3", "L4"].map((l) => ({ value: l, label: l }))}
      />
      <Select
        allowClear
        placeholder="对话轮数"
        value={filters.turns}
        onChange={(v) => setFilters((f) => ({ ...f, turns: v }))}
        options={[
          { value: "single", label: "单轮" },
          { value: "multi", label: "多轮" },
        ]}
      />
      <Select
        allowClear
        placeholder="稳定性"
        value={filters.stability}
        onChange={(v) => setFilters((f) => ({ ...f, stability: v }))}
        options={[
          { value: "stable_pass", label: "稳过" },
          { value: "flaky", label: "抖动" },
          { value: "stable_fail", label: "稳挂" },
        ]}
      />
      <Select
        allowClear
        placeholder="指南匹配率"
        value={filters.guideline}
        onChange={(v) => setFilters((f) => ({ ...f, guideline: v }))}
        options={[
          { value: "full", label: "100%" },
          { value: "partial", label: "<100%" },
          { value: "none", label: "无指南锚点" },
        ]}
      />
      <div className="case-toolbar__right">
        {hasActiveFilters && (
          <DashTableLink onClick={resetFilters}>重置</DashTableLink>
        )}
        <span className="case-toolbar__switch">
          <Switch
            size="small"
            checked={onlyPending}
            onChange={setOnlyPending}
            disabled={queueIds.size === 0}
          />
          仅看待审
        </span>
      </div>
    </div>
  );
}
