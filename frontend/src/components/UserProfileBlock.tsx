import { Typography } from "antd";
import type { CSSProperties } from "react";

const profileRootStyle: CSSProperties = {
  display: "grid",
  gap: 8,
  padding: "12px 14px",
  border: "1px solid var(--border-strong)",
  borderRadius: 8,
  background: "var(--surface-subtle)",
};

const profileRowsStyle: CSSProperties = {
  display: "grid",
  gap: 6,
};

const profileRowStyle: CSSProperties = {
  display: "grid",
  gridTemplateColumns: "96px minmax(0, 1fr)",
  gap: 12,
  alignItems: "start",
};

const profileValueStyle: CSSProperties = {
  whiteSpace: "pre-wrap",
  overflowWrap: "anywhere",
};

export function UserProfileBlock({ text, showTitle = true }: { text: string; showTitle?: boolean }) {
  const rows = text
    .split("\n")
    .map((line) => line.trim())
    .filter(Boolean)
    .map((line) => {
      const match = line.match(/^([^：:]{1,16})[：:]\s*(.*)$/);
      return match
        ? { label: match[1].trim(), value: match[2].trim() || "-" }
        : { label: "", value: line };
    });

  if (!rows.length) return null;

  return (
    <div style={profileRootStyle}>
      {showTitle ? <Typography.Text strong>用户档案</Typography.Text> : null}
      <div style={profileRowsStyle}>
        {rows.map((row, index) => (
          <div key={`${row.label}-${index}`} style={profileRowStyle}>
            {row.label ? (
              <Typography.Text type="secondary">{row.label}</Typography.Text>
            ) : (
              <span />
            )}
            <Typography.Text style={profileValueStyle}>{row.value}</Typography.Text>
          </div>
        ))}
      </div>
    </div>
  );
}
