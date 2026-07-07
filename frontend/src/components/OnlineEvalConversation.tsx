import { Space, Typography } from "antd";
import type { OnlineEvalCase } from "../api/index";
import {
  buildOnlineEvalConversationRounds,
  onlineEvalRoleLabel,
} from "../utils/onlineEvalConversation";
import { FeishuRichText } from "./FeishuRichText";
import { UserProfileBlock } from "./UserProfileBlock";

function TextBlock({ title, text, richText }: { title: string; text: string; richText?: unknown[] }) {
  return (
    <div style={{ display: "grid", gap: 8 }}>
      <Typography.Text strong>{title}</Typography.Text>
      <FeishuRichText text={text} richText={richText} />
    </div>
  );
}

export function OnlineEvalConversation({ row }: { row: OnlineEvalCase }) {
  const rounds = buildOnlineEvalConversationRounds(row);
  const userProfile = (row.user_profile || "").trim();
  if (!rounds.length && !userProfile) {
    return <Typography.Text type="secondary">-</Typography.Text>;
  }

  return (
    <Space direction="vertical" size={18} style={{ width: "100%" }}>
      {userProfile ? <UserProfileBlock text={userProfile} /> : null}
      {rounds.map((round, index) => (
        <Space key={index} direction="vertical" size={12} style={{ width: "100%" }}>
          <Typography.Text type="secondary">第 {index + 1} 轮</Typography.Text>
          <TextBlock title="用户问题" text={round.user || ""} richText={round.userRichText} />
          <TextBlock title="Cx 回复" text={round.assistant || ""} richText={round.assistantRichText} />
          {round.extras.map((message, extraIndex) => (
            <TextBlock
              key={`${message.role}-${extraIndex}`}
              title={onlineEvalRoleLabel(message.role)}
              text={message.content}
              richText={message.richText}
            />
          ))}
        </Space>
      ))}
    </Space>
  );
}
