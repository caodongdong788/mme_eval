export interface DimensionScorePoint {
  name: string;
  value: number;
}

/** 将后端八维均分规范为图表数据；空值不应被 Number(null) 错当成 0 分。 */
export function buildDimensionScoreData(
  averages: Record<string, unknown>,
  labels: Record<string, string>
): DimensionScorePoint[] {
  return Object.entries(averages).flatMap(([key, rawValue]) => {
    if (typeof rawValue !== "number" || !Number.isFinite(rawValue)) return [];
    return [{ name: labels[key] || key, value: Number(rawValue.toFixed(2)) }];
  });
}
