# Proposal: 移除手动入队 HITL + 展示默认判分模型

## Why

- 产品不需要「手动把通过题加入审核队列」；删除 `request-review` 全链路以保持代码整洁。
- 发起评测页应展示 `config.yaml` 默认判分模型（`GET /config/judge-defaults`）。

## What Changes

- 删除 `POST .../request-review`、`review_requested` 列与 `manual` 入队规则
- 前端 `api.requestReview` 删除；`useLaunchPage` 拉取并展示 `getJudgeDefaults`
- 更新 OpenSpec / README / server/README

## Non-Goals

- 不删 HITL 自动入队、annotate、review-queue 其余能力
