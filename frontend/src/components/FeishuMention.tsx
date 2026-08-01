interface FeishuMentionProps {
  name?: string | null;
}

export function FeishuMention({ name }: FeishuMentionProps) {
  const displayName = name?.trim();
  if (!displayName) {
    return <span className="feishu-mention--empty">—</span>;
  }

  return (
    <span
      className="feishu-mention"
      aria-label={`@${displayName}`}
      title={`飞书用户：${displayName}`}
    >
      <span className="feishu-mention__at" aria-hidden="true">
        @
      </span>
      <span>{displayName}</span>
    </span>
  );
}
