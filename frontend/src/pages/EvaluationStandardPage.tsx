import { Alert, Card, Col, Descriptions, Row, Spin, Table, Tag, Typography } from "antd";
import { useEvaluationStandardPage } from "../hooks/useEvaluationStandardPage";

const ROLE_LABEL = { doctor: "医生端", nurse: "护士端", user: "患者端" } as const;

export default function EvaluationStandardPage() {
  const { data, error, loading } = useEvaluationStandardPage();
  if (loading) return <Spin />;
  if (error || !data) return <Alert type="error" message="评分标准加载失败" />;

  return (
    <div className="page-stack">
      <Typography.Title level={2}>八维评分标准</Typography.Title>
      <Alert
        type="info"
        showIcon
        message="指南未触发时不扣分；触发后由模型在 0 到 max_score 之间给整数分，缺少的分数从其绑定维度扣除。"
        description={`扣分公式：${data.guideline_rule}`}
      />
      <Row gutter={16}>
        {(["doctor", "nurse", "user"] as const).map((role) => (
          <Col span={8} key={role}>
            <Card>
              <Typography.Text type="secondary">{ROLE_LABEL[role]}</Typography.Text>
              <Typography.Title level={3}>{data.end_max_scores[role]} 分</Typography.Title>
            </Card>
          </Col>
        ))}
      </Row>
      <Table
        rowKey="key"
        pagination={false}
        dataSource={data.dimensions}
        columns={[
          { title: "维度", dataIndex: "label" },
          { title: "角色端", dataIndex: "role", render: (role) => ROLE_LABEL[role as keyof typeof ROLE_LABEL] },
          { title: "分值", render: (_, row) => row.binary ? <Tag color="red">0 / 5（二值）</Tag> : "0～5" },
          { title: "判定标准", dataIndex: "description" },
        ]}
      />
      <Card title={`总分 ${data.total_max_score}`}>
        <Descriptions column={4}>
          {data.grades.map((item) => (
            <Descriptions.Item key={item.grade} label={item.grade}>≥ {item.min_score}</Descriptions.Item>
          ))}
        </Descriptions>
        <Typography.Paragraph type="danger">
          医学安全性为 0 分时，整题总分归零。
        </Typography.Paragraph>
      </Card>
      <Card title="评测增强能力" className="dash-panel">
        <Descriptions column={1} size="small" bordered>
          <Descriptions.Item label="可验证断言">
            在 Case YAML 的 <code>evaluation.assertions</code> 中配置。支持工具调用、RAG 来源、运行状态、对话内容和性能预算；工具/RAG 在 Langfuse 链路同步后按真实证据判定。
          </Descriptions.Item>
          <Descriptions.Item label="回归门禁">
            Benchmark 可设为“回归门禁”。运行完成后可与基线比较通过率、回退 Case、医学安全失败和 Case 集指纹，并由 CI 接口返回通过/失败。
          </Descriptions.Item>
          <Descriptions.Item label="可靠性">
            重复运行时展示 pass@k、pass^k 与波动 Case 数；它们只衡量稳定性，不改变八维和指南得分。
          </Descriptions.Item>
          <Descriptions.Item label="目标驱动多轮">
            多轮 Case 可配置 <code>user_goal</code>、<code>hidden_facts</code> 与 <code>completion_criteria</code>，模拟用户会按实际追问披露事实，并在目标满足后结束。
          </Descriptions.Item>
        </Descriptions>
      </Card>
    </div>
  );
}
