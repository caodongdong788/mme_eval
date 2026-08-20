import { Result } from "antd";
import { ArrowLeftOutlined } from "@ant-design/icons";
import { Link, useNavigate, useParams } from "react-router-dom";
import { RunAttributionTab } from "../components/RunAttributionTab";
import { DashPanel } from "../components/DashPanel";

export default function AttributionTaskDetailPage() {
  const { runId, taskId } = useParams();
  const navigate = useNavigate();
  const runNumber = Number(runId);
  const taskNumber = Number(taskId);

  if (!Number.isFinite(runNumber) || !Number.isFinite(taskNumber)) {
    return (
      <div className="dash-page">
        <Result
          status="warning"
          title="归因任务地址无效"
          extra={<Link to="/runs">返回评测列表</Link>}
        />
      </div>
    );
  }

  return (
    <div className="dash-page attribution-task-detail-page">
      <DashPanel
        className="attribution-task-detail-header"
        title={
          <div>
            <Link
              className="attribution-task-detail-back"
              to={`/runs/${runNumber}?tab=attribution`}
            >
              <ArrowLeftOutlined /> 返回归因任务列表
            </Link>
            <h2>归因任务 #{taskNumber}</h2>
            <p>查看任务级优化总结，并逐条检查或重新归因 Case。</p>
          </div>
        }
      >
        <></>
      </DashPanel>

      <RunAttributionTab
        runId={runNumber}
        mode="detail"
        selectedTaskId={taskNumber}
        onSelectedTaskIdChange={(nextTaskId) => {
          if (nextTaskId) {
            navigate(`/runs/${runNumber}/attribution-tasks/${nextTaskId}`);
          } else {
            navigate(`/runs/${runNumber}?tab=attribution`);
          }
        }}
      />
    </div>
  );
}
