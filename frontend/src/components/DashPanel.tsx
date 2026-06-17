import { ReactNode } from "react";

export interface DashPanelProps {
  title?: ReactNode;
  extra?: ReactNode;
  children: ReactNode;
  className?: string;
  bodyClassName?: string;
}

/** Dashboard 白卡分区：标题 + 内容，与 `.dash-panel` token 配套。 */
export function DashPanel({ title, extra, children, className, bodyClassName }: DashPanelProps) {
  const bodyClasses = ["dash-panel__body", bodyClassName].filter(Boolean).join(" ");
  return (
    <div className={["dash-panel", className].filter(Boolean).join(" ")}>
      {(title != null || extra) && (
        <div className="dash-panel__head">
          <div className="dash-panel__title-wrap">
            {typeof title === "string" ? <h3>{title}</h3> : title}
          </div>
          {extra}
        </div>
      )}
      <div className={bodyClasses}>{children}</div>
    </div>
  );
}
