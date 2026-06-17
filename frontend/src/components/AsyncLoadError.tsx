import { Button, Result } from "antd";

/** 列表/表单页统一的异步加载失败兜底（可重试）。 */
export function AsyncLoadError({
  message,
  onRetry,
}: {
  message: string;
  onRetry?: () => void;
}) {
  return (
    <div className="dash-table-card">
      <Result
        status="error"
        title="加载失败"
        subTitle={message}
        extra={
          onRetry ? (
            <Button type="primary" onClick={onRetry}>
              重试
            </Button>
          ) : undefined
        }
      />
    </div>
  );
}
