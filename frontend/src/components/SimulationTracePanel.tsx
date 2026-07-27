import { Tag, Typography } from "antd";
import { DashPanel } from "./DashPanel";

type SimulationEvent = {
  turn?: number;
  source?: string;
  id?: string;
  content?: string;
  facts_added?: Record<string, unknown>;
};

const SOURCE_LABEL: Record<string, string> = {
  opening: "开场",
  rule: "规则命中",
  scripted: "Benchmark 脚本",
  model: "模型补全",
};

export function SimulationTracePanel({ events }: { events?: SimulationEvent[] }) {
  if (!events?.length) return null;
  return (
    <DashPanel title="用户模拟路径">
      <div className="simulation-trace">
        {events.map((event, index) => (
          <div className="simulation-trace__row" key={`${event.turn}-${event.id}-${index}`}>
            <Tag color={event.source === "model" ? "purple" : "blue"}>
              {SOURCE_LABEL[event.source || ""] || event.source || "模拟"}
            </Tag>
            <Typography.Text type="secondary">第 {event.turn || index + 1} 轮</Typography.Text>
            {event.id ? <Typography.Text type="secondary">· {event.id}</Typography.Text> : null}
            {event.content ? <div className="simulation-trace__content">{event.content}</div> : null}
            {event.facts_added && Object.keys(event.facts_added).length ? (
              <Typography.Text type="secondary">新增运行态事实：{Object.entries(event.facts_added).map(([key, value]) => `${key}=${String(value)}`).join("；")}</Typography.Text>
            ) : null}
          </div>
        ))}
      </div>
    </DashPanel>
  );
}
