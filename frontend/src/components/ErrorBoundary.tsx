import { Component, type ErrorInfo, type ReactNode } from "react";
import { Button, Result } from "antd";
import { humanizeErrorText } from "../utils/apiError";

interface Props {
  children: ReactNode;
}

interface State {
  hasError: boolean;
  message?: string;
}

// 应用级错误边界：任何渲染期未捕获异常都降级为可读提示，避免整页白屏。
export class ErrorBoundary extends Component<Props, State> {
  state: State = { hasError: false };

  static getDerivedStateFromError(error: unknown): State {
    return {
      hasError: true,
      message: humanizeErrorText(
        error instanceof Error ? error.message : error,
        "页面显示时发生异常，请刷新页面重试。",
      ),
    };
  }

  componentDidCatch(error: Error, info: ErrorInfo): void {
    console.error("UI 渲染异常：", error, info.componentStack);
  }

  render(): ReactNode {
    if (this.state.hasError) {
      return (
        <Result
          status="error"
          title="页面出错了"
          subTitle={this.state.message || "渲染时发生未预期错误，请刷新重试。"}
          extra={
            <Button type="primary" onClick={() => window.location.reload()}>
              刷新页面
            </Button>
          }
        />
      );
    }
    return this.props.children;
  }
}
