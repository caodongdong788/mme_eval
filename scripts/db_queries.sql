-- MME 平台数据库常用查询
-- 用法见仓库根目录对话说明；Docker / SQLite 命令见文件头注释。
--
-- Docker Postgres（你当前 docker compose 环境）:
--   docker compose exec db psql -U medeval -d medeval -f - < scripts/db_queries.sql
-- 或单条:
--   docker compose exec db psql -U medeval -d medeval -c "SELECT ..."
--
-- 本机 SQLite（dev_platform）:
--   sqlite3 medeval_platform.db < scripts/db_queries.sql

-- =============================================================================
-- 0. 元信息
-- =============================================================================

-- 列出所有表
-- Postgres: \dt
-- SQLite:   .tables

-- =============================================================================
-- 1. 评测列表（对应前台「评测列表」）
-- =============================================================================

SELECT
    id,
    name,
    run_slug,
    status,
    round(CAST(pass_rate * 100 AS DECIMAL), 1) AS pass_pct,
    passed || '/' || total   AS pass_count,
    hard_gate_failed,
    n_runs,
    has_traces,
    pinned,
    parent_run_id,
    created_at
FROM eval_run
ORDER BY id DESC;

-- =============================================================================
-- 2. 某次 run 详情（把 :run_id 换成数字，如 15）
-- =============================================================================

-- SELECT id, name, run_slug, status, total, passed, pass_rate,
--        hard_gate_failed, grading, judge_fingerprints, config_snapshot,
--        parent_run_id, diff_against_run_id, created_at, finished_at
-- FROM eval_run
-- WHERE id = 15;

-- =============================================================================
-- 3. run 与磁盘目录对照（run_slug = outputs 子目录名）
-- =============================================================================

SELECT id, name, run_slug, status, has_traces
FROM eval_run
ORDER BY created_at DESC;

-- =============================================================================
-- 4. 某 run 失败 / 未上线用例
-- =============================================================================

-- SELECT sample_id, scenario, level, score_profile,
--        release_passed, hard_gate_passed, gate_passed,
--        composite_score, grade, failure_tags, needs_human_review
-- FROM case_result
-- WHERE run_id = 15 AND release_passed = false
-- ORDER BY sample_id;

-- =============================================================================
-- 5. 各 run 用例数统计
-- =============================================================================

SELECT
    r.id,
    r.name,
    count(c.id)              AS case_rows,
    sum(CASE WHEN c.release_passed THEN 1 ELSE 0 END) AS released_pass
FROM eval_run r
LEFT JOIN case_result c ON c.run_id = r.id
GROUP BY r.id, r.name
ORDER BY r.id DESC;

-- =============================================================================
-- 6. 重判 / 续跑血缘
-- =============================================================================

SELECT
    child.id          AS child_id,
    child.name        AS child_name,
    child.run_slug    AS child_slug,
    parent.id         AS parent_id,
    parent.name       AS parent_name,
    parent.run_slug   AS parent_slug
FROM eval_run child
LEFT JOIN eval_run parent ON parent.id = child.parent_run_id
WHERE child.parent_run_id IS NOT NULL
ORDER BY child.id DESC;

-- =============================================================================
-- 7. 人审队列（需人审的用例）
-- =============================================================================

SELECT
    r.id AS run_id,
    r.name,
    c.sample_id,
    c.scenario,
    c.needs_human_review,
    c.release_passed,
    c.failure_tags
FROM case_result c
JOIN eval_run r ON r.id = c.run_id
WHERE c.needs_human_review = true
ORDER BY r.id DESC, c.sample_id;

-- =============================================================================
-- 8. 人审标注记录
-- =============================================================================

SELECT
    a.id,
    a.run_id,
    r.name AS run_name,
    a.sample_id,
    a.reviewer,
    a.verdict,
    a.comment,
    a.created_at
FROM case_annotation a
JOIN eval_run r ON r.id = a.run_id
ORDER BY a.created_at DESC
LIMIT 50;

-- =============================================================================
-- 9. Benchmark 列表
-- =============================================================================

SELECT id, name, source, case_count, storage_path, created_at
FROM benchmark
ORDER BY id;

-- =============================================================================
-- 10. Pairwise 对比任务
-- =============================================================================

SELECT
    pc.id,
    pc.status,
    a.id   AS run_a_id,
    a.name AS run_a_name,
    b.id   AS run_b_id,
    b.name AS run_b_name,
    pc.total_cases,
    pc.done_cases,
    pc.created_at
FROM pairwise_comparison pc
JOIN eval_run a ON a.id = pc.run_a_id
JOIN eval_run b ON b.id = pc.run_b_id
ORDER BY pc.id DESC;

-- =============================================================================
-- 11. 判分模型配置（不含 api_key 明文）
-- =============================================================================

SELECT id, name, provider, model, base_url,
       CASE WHEN api_key IS NOT NULL AND api_key != '' THEN 1 ELSE 0 END AS has_api_key,
       pairwise_concurrency, updated_at
FROM judge_model_config
ORDER BY id;

-- =============================================================================
-- 12. 上线阈值覆盖
-- =============================================================================

SELECT profile, composite_threshold, updated_by, updated_at
FROM release_threshold_config
ORDER BY profile;
