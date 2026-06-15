import { type ReactNode } from "react";

// 元数据胶囊（等宽小字），用于 run 元信息（judge 模型、N= 等）。样式见 styles.css .chip。
export function MetaChip({ children }: { children: ReactNode }) {
  return <span className="chip">{children}</span>;
}
