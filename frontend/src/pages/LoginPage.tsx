import { Button, Typography, Alert } from "antd";
import { HeartFilled } from "@ant-design/icons";
import { useEffect } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import { feishuLoginPath, sanitizeReturnTo } from "../auth/redirect";

const { Title, Paragraph } = Typography;

export default function LoginPage() {
  const { user, loading } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const params = new URLSearchParams(location.search);
  const error = params.get("error");
  const returnTo = sanitizeReturnTo(params.get("redirect_to"));

  useEffect(() => {
    if (!loading && user) navigate(returnTo, { replace: true });
  }, [loading, user, navigate, returnTo]);

  return (
    <div className="login-wrap">
      <div className="login-card">
        <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 18 }}>
          <span className="app-brand-mark" style={{ width: 40, height: 40, fontSize: 20 }}>
            <HeartFilled />
          </span>
          <div style={{ lineHeight: 1.2 }}>
            <div style={{ fontSize: 11, letterSpacing: "0.12em", textTransform: "uppercase", color: "var(--muted)" }}>
              MME
            </div>
            <Title level={4} style={{ margin: 0 }}>
              Agent 评测平台
            </Title>
          </div>
        </div>
        <Paragraph type="secondary" style={{ marginBottom: 24 }}>
          医疗 Agent 安全评测与人工审核平台。使用飞书账号登录以继续。
        </Paragraph>
        {error && (
          <Alert
            type="error"
            showIcon
            style={{ marginBottom: 16, textAlign: "left" }}
            message="登录失败"
            description={decodeURIComponent(error)}
          />
        )}
        <Button
          type="primary"
          size="large"
          block
          onClick={() => {
            window.location.href = feishuLoginPath(returnTo);
          }}
        >
          用飞书登录
        </Button>
      </div>
    </div>
  );
}
