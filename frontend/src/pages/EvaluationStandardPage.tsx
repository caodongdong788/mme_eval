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
    </div>
  );
}
