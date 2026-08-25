export type ProfileMemoryCategory = "关注" | "习惯" | "沟通" | "背景";

export type ProfileMemoryCategoryOption = {
  value: ProfileMemoryCategory;
  description: string;
};

export const PROFILE_MEMORY_CATEGORY_OPTIONS: ProfileMemoryCategoryOption[] = [
  { value: "关注", description: "用户长期关注、担忧或希望持续留意的事情" },
  { value: "习惯", description: "稳定的生活习惯、行为方式或日常偏好" },
  { value: "沟通", description: "称呼、语气、回答结构和沟通方式偏好" },
  { value: "背景", description: "会长期影响服务的家庭、工作或照护背景" },
];

const VALID_CATEGORIES = new Set<ProfileMemoryCategory>(
  PROFILE_MEMORY_CATEGORY_OPTIONS.map((item) => item.value),
);

const LEGACY_CATEGORY_ALIASES: Record<string, ProfileMemoryCategory> = {
  心理: "关注",
};

export function parseProfileMemoryEntry(value: unknown): {
  category?: ProfileMemoryCategory;
  content: string;
} {
  const text = String(value ?? "");
  const match = text.match(/^\s*\[([^\]]+)]\s*(.*)$/s);
  if (!match) return { content: text };
  const sourceCategory = match[1].trim();
  const category = VALID_CATEGORIES.has(sourceCategory as ProfileMemoryCategory)
    ? sourceCategory as ProfileMemoryCategory
    : LEGACY_CATEGORY_ALIASES[sourceCategory];
  return category
    ? { category, content: match[2] }
    : { content: text };
}

export function formatProfileMemoryEntry(category: ProfileMemoryCategory | undefined, content: string): string {
  return category ? `[${category}] ${content.trimStart()}` : content;
}
