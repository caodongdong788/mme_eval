import { ReactElement } from "react";
import { render, RenderOptions } from "@testing-library/react";
import { ConfigProvider } from "antd";
import zhCN from "antd/locale/zh_CN";

export function renderWithProviders(ui: ReactElement, options?: Omit<RenderOptions, "wrapper">) {
  return render(<ConfigProvider locale={zhCN}>{ui}</ConfigProvider>, options);
}
