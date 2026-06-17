import { ReactNode, type AnchorHTMLAttributes, type MouseEventHandler } from "react";
import { Link, type LinkProps } from "react-router-dom";
import { Space } from "antd";

const linkClass = (className?: string, extra?: string) =>
  [extra, className].filter(Boolean).join(" ");

/** 表格内路由链接（紫色纯文本链，与评测列表「看板」一致）。 */
export function DashTableNavLink({ className, ...props }: LinkProps) {
  return <Link className={linkClass(className, "dash-table__link")} {...props} />;
}

type DashTableLinkProps = {
  children: ReactNode;
  disabled?: boolean;
  className?: string;
  href?: string;
  onClick?: MouseEventHandler<HTMLAnchorElement>;
} & Omit<AnchorHTMLAttributes<HTMLAnchorElement>, "children" | "onClick" | "href">;

/** 表格内主操作（紫色纯文本链；非路由用 onClick）。 */
export function DashTableLink({
  children,
  disabled,
  className,
  href,
  onClick,
  ...rest
}: DashTableLinkProps) {
  const cls = linkClass(className, "dash-table__link");
  if (href) {
    return (
      <a className={cls} aria-disabled={disabled} href={href} onClick={onClick} {...rest}>
        {children}
      </a>
    );
  }
  return (
    <a
      role="button"
      tabIndex={disabled ? -1 : 0}
      className={cls}
      aria-disabled={disabled || undefined}
      onClick={(e) => {
        if (disabled) {
          e.preventDefault();
          return;
        }
        onClick?.(e);
      }}
      onKeyDown={(e) => {
        if (disabled) return;
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          onClick?.(e as unknown as React.MouseEvent<HTMLAnchorElement>);
        }
      }}
      {...rest}
    >
      {children}
    </a>
  );
}

type DashTableDangerLinkProps = {
  children: ReactNode;
  disabled?: boolean;
  className?: string;
  onClick?: MouseEventHandler<HTMLAnchorElement>;
};

/** 表格内危险操作（红色纯文本链，可含图标）。 */
export function DashTableDangerLink({
  children,
  disabled,
  className,
  onClick,
}: DashTableDangerLinkProps) {
  const cls = linkClass(className, "dash-table__danger-link");
  return (
    <a
      role="button"
      tabIndex={disabled ? -1 : 0}
      className={cls}
      aria-disabled={disabled || undefined}
      onClick={(e) => {
        if (disabled) {
          e.preventDefault();
          return;
        }
        onClick?.(e);
      }}
      onKeyDown={(e) => {
        if (disabled) return;
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          onClick?.(e as unknown as React.MouseEvent<HTMLAnchorElement>);
        }
      }}
    >
      {children}
    </a>
  );
}

/** 表格「操作」列内链式按钮组，统一间距。 */
export function DashTableActions({ children }: { children: ReactNode }) {
  return (
    <Space size={12} className="dash-table-actions">
      {children}
    </Space>
  );
}
