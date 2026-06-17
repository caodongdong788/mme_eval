import { ReactNode } from "react";

export interface DashboardPageShellProps {
  title: string;
  sub?: ReactNode;
  extra?: ReactNode;
  centered?: boolean;
  children: ReactNode;
}

/** Coze 风数据页外壳：浅灰底 + 顶栏标题；与 `.dash-page` / `--runs-*` token 配套。 */
export function DashboardPageShell({
  title,
  sub,
  extra,
  centered,
  children,
}: DashboardPageShellProps) {
  return (
    <div className={centered ? "dash-page dash-page--centered" : "dash-page"}>
      <div className="dash-page__head">
        <div>
          <h1 className="dash-page__title">{title}</h1>
          {sub ? <p className="dash-page__sub">{sub}</p> : null}
        </div>
        {extra ? <div className="dash-page__actions">{extra}</div> : null}
      </div>
      {children}
    </div>
  );
}
