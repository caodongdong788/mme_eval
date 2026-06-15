import { lazy, Suspense, type ReactNode } from "react";
import { Avatar, Breadcrumb, Dropdown, Layout, Menu, Spin } from "antd";
import {
  DatabaseOutlined,
  ExperimentOutlined,
  HeartFilled,
  LineChartOutlined,
  LogoutOutlined,
  RocketOutlined,
  SlidersOutlined,
  SwapOutlined,
  UnorderedListOutlined,
  UserOutlined,
} from "@ant-design/icons";
import { Link, Navigate, Route, Routes, useLocation } from "react-router-dom";
import LoginPage from "./pages/LoginPage";
import RequireAuth from "./auth/RequireAuth";
import { useAuth } from "./auth/AuthContext";
import { api } from "./api";

// 路由级懒加载：按页分包，首屏只加载登录/壳层，其余页面按需异步拉取。
const BenchmarksPage = lazy(() => import("./pages/BenchmarksPage"));
const JudgeModelsPage = lazy(() => import("./pages/JudgeModelsPage"));
const ReleaseThresholdsPage = lazy(() => import("./pages/ReleaseThresholdsPage"));
const LaunchPage = lazy(() => import("./pages/LaunchPage"));
const RunsPage = lazy(() => import("./pages/RunsPage"));
const RunDashboardPage = lazy(() => import("./pages/RunDashboardPage"));
const CaseDetailPage = lazy(() => import("./pages/CaseDetailPage"));
const PairwisePage = lazy(() => import("./pages/PairwisePage"));
const PairwiseDetailPage = lazy(() => import("./pages/PairwiseDetailPage"));
const TrendsPage = lazy(() => import("./pages/TrendsPage"));

const { Sider, Content } = Layout;

const MENU = [
  {
    type: "group" as const,
    label: "评测",
    children: [
      { key: "/runs", icon: <UnorderedListOutlined />, label: <Link to="/runs">评测列表</Link> },
      { key: "/trends", icon: <LineChartOutlined />, label: <Link to="/trends">趋势看板</Link> },
      { key: "/pairwise", icon: <SwapOutlined />, label: <Link to="/pairwise">Pairwise 对比</Link> },
    ],
  },
  {
    type: "group" as const,
    label: "资源",
    children: [
      { key: "/benchmarks", icon: <DatabaseOutlined />, label: <Link to="/benchmarks">Benchmark 库</Link> },
      { key: "/judge-models", icon: <ExperimentOutlined />, label: <Link to="/judge-models">判分模型</Link> },
      { key: "/release-thresholds", icon: <SlidersOutlined />, label: <Link to="/release-thresholds">阈值配置</Link> },
    ],
  },
  {
    type: "group" as const,
    label: "操作",
    children: [
      { key: "/launch", icon: <RocketOutlined />, label: <Link to="/launch">发起评测</Link> },
    ],
  },
];

const SECTION_LABEL: Record<string, string> = {
  runs: "评测列表",
  trends: "趋势看板",
  benchmarks: "Benchmark 库",
  "judge-models": "判分模型",
  "release-thresholds": "阈值配置",
  launch: "发起评测",
  pairwise: "Pairwise 对比",
};

function useBreadcrumb() {
  const { pathname } = useLocation();
  const parts = pathname.split("/").filter(Boolean);
  const items: { title: ReactNode }[] = [{ title: "评测平台" }];
  if (parts.length === 0) return items;
  const section = parts[0];
  items.push({
    title:
      section === "runs" && parts.length > 1 ? (
        <Link to="/runs">评测列表</Link>
      ) : (
        SECTION_LABEL[section] || section
      ),
  });
  if (section === "runs" && parts[1]) {
    items.push({ title: parts.length >= 4 ? <Link to={`/runs/${parts[1]}`}>{`运行 #${parts[1]}`}</Link> : `运行 #${parts[1]}` });
  }
  if (section === "runs" && parts[3]) {
    items.push({ title: "用例明细" });
  }
  return items;
}

function UserBar() {
  const { user, refresh } = useAuth();
  if (!user) return null;
  const onLogout = async () => {
    await api.logout();
    await refresh();
    window.location.href = "/login";
  };
  return (
    <Dropdown
      placement="bottomRight"
      menu={{ items: [{ key: "logout", icon: <LogoutOutlined />, label: "退出登录", onClick: onLogout }] }}
    >
      <div className="app-userbar app-userbar--header">
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <Avatar size={30} src={user.avatar_url || undefined} icon={<UserOutlined />} />
          <div style={{ lineHeight: 1.2, overflow: "hidden" }}>
            <div style={{ fontSize: 13, fontWeight: 600, color: "var(--ink)", whiteSpace: "nowrap", textOverflow: "ellipsis", overflow: "hidden" }}>
              {user.name}
            </div>
            <div style={{ fontSize: 11, color: "var(--muted)" }}>已登录 · 飞书</div>
          </div>
        </div>
      </div>
    </Dropdown>
  );
}

function MainLayout() {
  const location = useLocation();
  const selected = "/" + (location.pathname.split("/")[1] || "runs");
  const crumbs = useBreadcrumb();
  return (
    <Layout style={{ minHeight: "100vh" }}>
      <Sider theme="light" width={236} breakpoint="lg" collapsedWidth="0" className="app-sider">
        <div className="app-brand">
          <span className="app-brand-mark">
            <HeartFilled />
          </span>
          <span className="app-brand-text">
            <div className="app-brand-title">MME</div>
            <div className="app-brand-sub">Agent 评测平台</div>
          </span>
        </div>
        <Menu mode="inline" selectedKeys={[selected]} items={MENU} style={{ borderInlineEnd: "none" }} />
      </Sider>
      <Layout>
        <Layout.Header style={{ paddingInline: 36 }}>
          <div className="app-content-head">
            <Breadcrumb items={crumbs} />
            <UserBar />
          </div>
        </Layout.Header>
        <Content style={{ margin: "28px 36px 40px" }}>
          <Suspense
            fallback={
              <div style={{ display: "flex", justifyContent: "center", padding: "80px 0" }}>
                <Spin />
              </div>
            }
          >
            <Routes>
              <Route path="/" element={<Navigate to="/runs" replace />} />
              <Route path="/runs" element={<RunsPage />} />
              <Route path="/runs/:runId" element={<RunDashboardPage />} />
              <Route path="/runs/:runId/cases/:sampleId" element={<CaseDetailPage />} />
              <Route path="/pairwise" element={<PairwisePage />} />
              <Route path="/pairwise/:comparisonId" element={<PairwiseDetailPage />} />
              <Route path="/launch" element={<LaunchPage />} />
              <Route path="/benchmarks" element={<BenchmarksPage />} />
              <Route path="/judge-models" element={<JudgeModelsPage />} />
              <Route path="/release-thresholds" element={<ReleaseThresholdsPage />} />
              <Route path="/trends" element={<TrendsPage />} />
            </Routes>
          </Suspense>
        </Content>
      </Layout>
    </Layout>
  );
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route
        path="/*"
        element={
          <RequireAuth>
            <MainLayout />
          </RequireAuth>
        }
      />
    </Routes>
  );
}
