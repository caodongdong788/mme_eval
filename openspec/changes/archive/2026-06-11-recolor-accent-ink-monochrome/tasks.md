# Tasks

## 1. 设计契约（先于代码）
- [x] 1.1 `DESIGN.md`：frontmatter `primary`/`primary-soft`/`chart-accent` 改墨黑；narrative + Primary + One Lamp + Ink&Paper + Buttons/Status/Inputs/Menu/Charts + Do/Don't 去 teal
- [x] 1.2 `.impeccable/design.json`：`colorMeta.primary`、按钮/输入 CSS、overview、narrative、namedRules、do/don't 同步去 teal

## 2. Token 镜像（单一信任源）
- [x] 2.1 `styles.css :root`：`--primary*` 改墨黑（#111827 / #374151 / #F3F4F6 / #E5E7EB / #EEF0F3）+ 链接 hover 下划线
- [x] 2.2 `theme.ts`：`palette.primary*`、`colorPrimary/Hover/Active`、`colorLink/Hover`、`palette.chart.{teal→#111827, ink→#6B7280}`

## 3. 页面统一
- [x] 3.1 `LaunchPage`：主按钮去 `size="large"`、加 RocketOutlined 图标与列表页一致；两卡保持无边框极简

## 4. Spec delta
- [x] 4.1 `specs/eval-platform-dashboard/spec.md`：MODIFIED「看板视觉设计契约」——强调色 teal→墨黑

## 5. 验证
- [x] 5.1 `npm run typecheck` + `npm run build` 通过
- [x] 5.2 裸 hex 扫描（业务代码无散落 teal/绿色）
- [x] 5.3 `graphify update .` 刷新
- [x] 5.4 `openspec validate --strict` 通过
