import { Tag, Typography } from "antd";
import {
  accountInitializationModules,
  findConversationContextReferences,
  type AssistantMessage,
  type ConversationContextInitialState,
} from "../utils/conversationContext";

export type { ConversationContextInitialState } from "../utils/conversationContext";

export function AccountInitializationDetails({
  initialState,
  messages = [],
}: {
  initialState?: ConversationContextInitialState;
  messages?: AssistantMessage[];
}) {
  const references = findConversationContextReferences(initialState, messages);
  const modules = accountInitializationModules(initialState);
  if (!modules.length) return <div className="conversation-context-empty">该 Case 未配置账号初始化数据</div>;
  return (
    <div className="conversation-context-modules">
      {modules.map((module) => (
        <section className="conversation-context-module" key={module.key}>
          <header><Typography.Text strong>{module.label}</Typography.Text><span>{module.entries.length} 项</span></header>
          <div className="conversation-context-rows conversation-context-rows--injected">
            {module.entries.map((entry, index) => {
              const match = entry.referenceKind
                ? references.find((reference) => reference.kind === entry.referenceKind && reference.label === entry.label)
                : undefined;
              return (
                <article className="conversation-context-row" key={`${entry.label}-${index}`}>
                  <div className="conversation-context-row__head">
                    <strong>{entry.label}</strong>
                    <span><Tag color="blue">已初始化</Tag>{match?.turns.map((turn) => <Tag key={turn}>回复 {turn} 命中</Tag>)}</span>
                  </div>
                  <p>{entry.content}</p>
                  {match ? <small>回答命中：{match.evidence}</small> : null}
                </article>
              );
            })}
          </div>
        </section>
      ))}
    </div>
  );
}

export function ConversationContextReferences({
  initialState,
  messages,
}: {
  initialState?: ConversationContextInitialState;
  messages: AssistantMessage[];
}) {
  return (
    <div className="conversation-context-references">
      <p className="conversation-context-note">展示本次评测实际初始化到账号的全部数据；“回复命中”只对用户档案和过往事实进行可核对标记。</p>
      <AccountInitializationDetails initialState={initialState} messages={messages} />
    </div>
  );
}
