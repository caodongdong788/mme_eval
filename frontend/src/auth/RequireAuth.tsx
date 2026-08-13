import { Spin } from "antd";
import { Navigate, useLocation } from "react-router-dom";
import { useAuth } from "./AuthContext";
import type { ReactNode } from "react";
import { loginPath } from "./redirect";

export default function RequireAuth({ children }: { children: ReactNode }) {
  const { loading, authRequired, user } = useAuth();
  const location = useLocation();
  if (loading) {
    return (
      <div style={{ display: "flex", justifyContent: "center", padding: 80 }}>
        <Spin size="large" />
      </div>
    );
  }
  // 仅当后端开启强制登录且未登录时拦截；dev 未配密钥则放行。
  if (authRequired && !user) {
    const returnTo = `${location.pathname}${location.search}${location.hash}`;
    return <Navigate to={loginPath(returnTo)} replace />;
  }
  return <>{children}</>;
}
