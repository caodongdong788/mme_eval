import { useMemo } from "react";
import { Button, Descriptions, Empty, Result, Spin, Tag } from "antd";
import { Link, useParams } from "react-router-dom";
import { AttributionDetail } from "../components/RunAttributionTab";
import { DashPanel } from "../components/DashPanel";
import { formatApiDateTime } from "../utils/datetime";
import { useAttributionCaseDetail } from "../hooks/useAttributionCaseDetail";

export default function AttributionCaseDetailPage() {
  const { runId, taskId, sampleId } = useParams();
  const runNumber = Number(runId);
  const taskNumber = Number(taskId);
  const decodedSampleId = useMemo(
    () => decodeURIComponent(sampleId || ""),
    [sampleId]
  );
  const { task, result, error } = useAttributionCaseDetail(
    runNumber,
    taskNumber,
    decodedSampleId
  );

  const item = task?.items.find(
    (candidate) => candidate.sample_id === decodedSampleId
  );
  const taskDetailPath = `/runs/${runNumber}/attribution-tasks/${taskNumber}`;
  const originalCasePath = `/runs/${runNumber}/cases/${encodeURIComponent(decodedSampleId)}`;

  if (error) {
    return (
      <div className="dash-page">
        <Result
          status="warning"
          title="无法加载归因结果"
          subTitle={error}
          extra={<Link to={taskDetailPath}>返回归因任务</Link>}
        />
      </div>
    );
  }
  if (!task || !result) {
    return (
      <div className="dash-page attribution-result-page attribution-result-page--loading">
        <Spin size="large" />
      </div>
    );
  }

  return (
    <div className="dash-page attribution-result-page">
      <DashPanel
        title={
          <Link to={taskDetailPath} className="dash-table__link">
            ← 返回归因任务
          </Link>
        }
        extra={
          <Button
            href={originalCasePath}
            target="_blank"
            rel="noopener noreferrer"
          >
            查看原用例
          </Button>
        }
      >
        <Descriptions
          title={`${decodedSampleId} · 归因结果`}
          column={{ xs: 1, md: 2, lg: 4 }}
          size="small"
        >
          <Descriptions.Item label="归因任务">#{task.id}</Descriptions.Item>
          <Descriptions.Item label="分析模型">
            {task.judge_model_name || `模型 #${task.judge_model_id}`}
          </Descriptions.Item>
          <Descriptions.Item label="场景">
            {item?.scenario || "—"}
          </Descriptions.Item>
          <Descriptions.Item label="类别">
            {item?.case_type || "—"}
          </Descriptions.Item>
          <Descriptions.Item label="状态">
            <Tag color="success">已完成</Tag>
          </Descriptions.Item>
          <Descriptions.Item label="创建时间">
            {formatApiDateTime(task.created_at)}
          </Descriptions.Item>
        </Descriptions>
      </DashPanel>

      {result.available ? (
        <DashPanel title="归因结论与优化建议">
          <AttributionDetail result={result} />
        </DashPanel>
      ) : (
        <DashPanel title="归因结论与优化建议">
          <Empty description="该用例暂无可查看的归因结果" />
        </DashPanel>
      )}
    </div>
  );
}
