import {
  CheckCircleFilled,
  HeartOutlined,
  MedicineBoxOutlined,
  SafetyCertificateOutlined,
  SyncOutlined,
} from "@ant-design/icons";
import { Alert, Card, Col, Collapse, Row, Spin, Tabs, Tag } from "antd";
import { useState, type ReactNode } from "react";
import type { EvaluationStandard } from "../api";
import { AsyncLoadError } from "../components/AsyncLoadError";
import { DashboardPageShell } from "../components/DashboardPageShell";
import { useEvaluationStandardPage } from "../hooks/useEvaluationStandardPage";

const ROLE_ICONS: Record<"doctor" | "nurse" | "user", ReactNode> = {
  doctor: <SafetyCertificateOutlined />,
  nurse: <MedicineBoxOutlined />,
  user: <HeartOutlined />,
};

const ENHANCEMENTS = [
  {
    key: "assertions",
    label: "可验证断言",
    children: (
      <p>
        在 Case YAML 的 <code>evaluation.assertions</code> 中配置。支持工具调用、RAG
        来源、运行状态、对话内容和性能预算；工具与 RAG 在链路同步后按真实证据判定。
      </p>
    ),
  },
  {
    key: "regression",
    label: "回归门禁",
    children: (
      <p>
        Benchmark 可设为回归门禁，运行完成后可与基线比较通过率、回退 Case、医学安全失败和
        Case 集指纹，并由 CI 接口返回通过或失败。
      </p>
    ),
  },
  {
    key: "reliability",
    label: "可靠性",
    children: (
      <p>
        重复运行时展示 pass@k、pass^k 与波动 Case 数；这些指标只衡量稳定性，不改变八维和指南得分。
      </p>
    ),
  },
  {
    key: "multi-turn",
    label: "目标驱动多轮",
    children: (
      <p>
        多轮 Case 可配置 <code>user_goal</code>、<code>hidden_facts</code> 与{" "}
        <code>completion_criteria</code>，模拟用户按实际追问披露事实，并在目标满足后结束。
      </p>
    ),
  },
];

function ModelComparisonStandard({
  standard,
}: {
  standard: EvaluationStandard["model_comparison"];
}) {
  return (
    <div className="evaluation-standard-comparison">
      <section className="evaluation-standard-hero" aria-label="模型对比评分体系总览">
        <div className="evaluation-standard-total">
          <span className="evaluation-standard-eyebrow">PAIRWISE STANDARD</span>
          <strong className="evaluation-standard-total__value mono">8</strong>
          <span className="evaluation-standard-total__unit">维</span>
          <p>逐题相对比较；不覆盖 CX 八维绝对分与上线门禁。</p>
        </div>
        <div className="evaluation-standard-roles">
          <article className="evaluation-standard-role-summary">
            <div className="evaluation-standard-role-icon evaluation-standard-role-icon--doctor">
              <SyncOutlined />
            </div>
            <div>
              <span>双盲换序</span>
              <strong>交换 A / B 再评一次</strong>
              <small>换序不一致时降低置信</small>
            </div>
          </article>
          <article className="evaluation-standard-role-summary">
            <div className="evaluation-standard-role-icon evaluation-standard-role-icon--nurse">
              <CheckCircleFilled />
            </div>
            <div>
              <span>等权决策</span>
              <strong>A / B / 持平 / N/A</strong>
              <small>N/A 不计入分母</small>
            </div>
          </article>
          <article className="evaluation-standard-role-summary">
            <div className="evaluation-standard-role-icon evaluation-standard-role-icon--user">
              <HeartOutlined />
            </div>
            <div>
              <span>性能观测</span>
              <strong>TTFT / 延迟 / Token</strong>
              <small>仅展示，不参与胜负</small>
            </div>
          </article>
        </div>
      </section>

      <Alert
        type="info"
        showIcon
        className="evaluation-standard-gate-alert"
        message="模型能力与响应性能分开判断"
        description={standard.ttft_rule}
      />

      <Row gutter={[16, 16]}>
        {standard.dimensions.map((dimension, index) => (
          <Col xs={24} lg={12} key={dimension.key}>
            <Card className="evaluation-standard-comparison-card">
              <div className="evaluation-standard-dimension__identity">
                <span className="evaluation-standard-dimension__number mono">
                  {String(index + 1).padStart(2, "0")}
                </span>
                <div>
                  <h3>{dimension.label}</h3>
                  <Tag color={dimension.applicability === "所有用例" ? "blue" : "default"}>
                    {dimension.applicability}
                  </Tag>
                </div>
              </div>
              <p>{dimension.description}</p>
            </Card>
          </Col>
        ))}
      </Row>

      <section className="evaluation-standard-enhancements">
        <div>
          <span className="evaluation-standard-eyebrow">DECISION RULE</span>
          <h2>严谨对比规则</h2>
          <p>{standard.overall_rule}</p>
        </div>
        <Collapse
          ghost
          expandIconPosition="end"
          items={[
            { key: "blind", label: "双盲换序与位置偏差控制", children: <p>{standard.blind_rule}</p> },
            { key: "ttft", label: "TTFT 与资源消耗", children: <p>{standard.ttft_rule}</p> },
            {
              key: "values",
              label: "逐维结论",
              children: (
                <p>{standard.values.map((item) => `${item.label}`).join("、")}；只有具备充分证据时才判一侧更好。</p>
              ),
            },
          ]}
        />
      </section>
    </div>
  );
}

export default function EvaluationStandardPage() {
  const { data, error, loading, reload } = useEvaluationStandardPage();
  const [activeStandard, setActiveStandard] = useState("cx_eight_dimension");

  if (loading) {
    return (
      <div className="evaluation-standard-loading">
        <Spin tip="正在同步评分标准" />
      </div>
    );
  }

  if (error || !data) {
    return (
      <DashboardPageShell title="八维评分标准">
        <AsyncLoadError message="评分标准加载失败" onRetry={reload} />
      </DashboardPageShell>
    );
  }

  const dimensionIndex = new Map(
    data.dimensions.map((dimension, index) => [dimension.key, index + 1]),
  );

  return (
    <DashboardPageShell
      title="评分标准"
      sub="CX 八维用于产品质量与上线门禁；模型对比八维用于公平比较不同基座能力。"
      extra={
        <span className="status-dot status-dot--pass evaluation-standard-sync">
          <SyncOutlined />
          已与当前 Judge 同步
        </span>
      }
    >
      <Tabs
        activeKey={activeStandard}
        onChange={setActiveStandard}
        items={[
          { key: "cx_eight_dimension", label: "CX 八维评分" },
          { key: "model_comparison", label: "模型对比八维" },
        ]}
      />

      {activeStandard === "model_comparison" ? (
        <ModelComparisonStandard standard={data.model_comparison} />
      ) : (
        <>
      <section className="evaluation-standard-hero" aria-label="评分体系总览">
        <div className="evaluation-standard-total">
          <span className="evaluation-standard-eyebrow">TOTAL SCORE</span>
          <strong className="evaluation-standard-total__value mono">
            {data.total_max_score}
          </strong>
          <span className="evaluation-standard-total__unit">分制</span>
          <p>三端归一后相加；安全 Gate 未通过时整题归零。</p>
        </div>

        <div className="evaluation-standard-roles">
          {data.roles.map((role) => (
            <article className="evaluation-standard-role-summary" key={role.key}>
              <div className={`evaluation-standard-role-icon evaluation-standard-role-icon--${role.key}`}>
                {ROLE_ICONS[role.key]}
              </div>
              <div>
                <span>{role.label}</span>
                <strong className="mono">{role.max_score} 分</strong>
                <small>
                  {role.dimension_count} 个维度
                  {role.normalized ? ` · 原始 ${role.raw_max_score} 分归一` : ""}
                </small>
              </div>
            </article>
          ))}
        </div>
      </section>

      {data.medical_safety_zeroes_total ? (
        <Alert
          className="evaluation-standard-gate-alert"
          type="error"
          showIcon
          message="医学安全性是 Safety Gate"
          description="该维度只允许 0 或 5 分；出现任一安全红线即判 0 分，并将整题总分归零。"
        />
      ) : null}

      <div className="evaluation-standard-layout">
        <main className="evaluation-standard-main">
          {data.roles.map((role) => {
            const dimensions = data.dimensions.filter((dimension) => dimension.role === role.key);
            const headingId = `standard-role-${role.key}`;

            return (
              <section
                className="evaluation-standard-role"
                key={role.key}
                aria-labelledby={headingId}
              >
                <header className="evaluation-standard-role__head">
                  <div>
                    <span className={`evaluation-standard-role-icon evaluation-standard-role-icon--${role.key}`}>
                      {ROLE_ICONS[role.key]}
                    </span>
                    <div>
                      <h2 id={headingId}>{role.label}</h2>
                      <p>
                        负责 {dimensions.map((dimension) => dimension.label).join("、")}
                      </p>
                    </div>
                  </div>
                  <strong className="mono">{role.max_score} 分</strong>
                </header>

                <div className="evaluation-standard-dimensions">
                  {dimensions.map((dimension) => (
                    <article
                      className={
                        dimension.binary
                          ? "evaluation-standard-dimension evaluation-standard-dimension--gate"
                          : "evaluation-standard-dimension"
                      }
                      key={dimension.key}
                    >
                      <div className="evaluation-standard-dimension__identity">
                        <span className="evaluation-standard-dimension__number mono">
                          {String(dimensionIndex.get(dimension.key)).padStart(2, "0")}
                        </span>
                        <div>
                          <h3>{dimension.label}</h3>
                          <span className="evaluation-standard-score-range mono">
                            {dimension.score_range}
                          </span>
                        </div>
                      </div>

                      <div className="evaluation-standard-dimension__criteria">
                        <p className="evaluation-standard-dimension__description">
                          {dimension.description}
                        </p>
                        <div className="evaluation-standard-boundaries">
                          <div>
                            <span className="evaluation-standard-boundary-label evaluation-standard-boundary-label--zero">
                              0 分边界
                            </span>
                            <p>{dimension.zero_score_description}</p>
                          </div>
                          <div>
                            <span className="evaluation-standard-boundary-label evaluation-standard-boundary-label--full">
                              5 分满分
                            </span>
                            <p>{dimension.full_score_description}</p>
                          </div>
                        </div>
                      </div>
                    </article>
                  ))}
                </div>
              </section>
            );
          })}
        </main>

        <aside className="evaluation-standard-aside" aria-label="评分规则补充">
          <section className="evaluation-standard-side-card">
            <div className="evaluation-standard-side-card__head">
              <span>通用评分锚点</span>
              <small>安全 Gate 除外</small>
            </div>
            <ol className="evaluation-standard-anchor-list">
              {data.score_anchors.map((anchor) => (
                <li key={anchor.score}>
                  <strong className="mono">{anchor.score}</strong>
                  <span>{anchor.description}</span>
                </li>
              ))}
            </ol>
          </section>

          <section className="evaluation-standard-side-card">
            <div className="evaluation-standard-side-card__head">
              <span>总分评级</span>
              <small>{data.total_max_score} 分制</small>
            </div>
            <div className="evaluation-standard-grade-list">
              {data.grades.map((grade) => (
                <div key={grade.grade}>
                  <span
                    className={grade.passed ? "status-dot status-dot--pass" : "status-dot status-dot--fail"}
                  >
                    {grade.grade}
                  </span>
                  <strong className="mono">≥ {grade.min_score}</strong>
                </div>
              ))}
            </div>
          </section>

          <section className="evaluation-standard-side-card evaluation-standard-guideline-card">
            <div className="evaluation-standard-side-card__head">
              <span>Case 指南扣分</span>
            </div>
            <p>{data.guideline_rule_description}</p>
            <code>{data.guideline_rule}</code>
          </section>
        </aside>
      </div>

      <section className="evaluation-standard-enhancements" aria-labelledby="evaluation-enhancements-title">
        <div>
          <span className="evaluation-standard-eyebrow">BEYOND SCORING</span>
          <h2 id="evaluation-enhancements-title">评测增强能力</h2>
          <p>这些能力补充证据、回归和稳定性判断，但不会改变八维与指南得分。</p>
        </div>
        <Collapse ghost items={ENHANCEMENTS} expandIconPosition="end" />
      </section>

      <p className="evaluation-standard-source-note">
        <CheckCircleFilled />
        页面内容由服务端当前评分定义实时生成，无需在前端重复维护判据文案。
      </p>
        </>
      )}
    </DashboardPageShell>
  );
}
