# MME 生产发布说明

本文说明 MME 的正式发布入口、当前实际发布行为、验证和回滚方式。生产代码只从 GitLab 发布。

## 发布原则

- 唯一生产代码源：`git@gitlab.soundws.com:cx/cx-mme.git`。
- 只允许推送 `gitlab/main`；`origin`（GitHub）不参与生产发布。
- GitLab Pipeline 使用 `mme-production` 资源锁，同一时间只允许一个发布进行。
- 发布不会重建数据库和数据卷。评测、重新评测和归因任务均以数据库中的任务记录与租约为准，Worker 重启后会继续领取未完成工作。
- `MEDEVAL_OPEN_API_ENCRYPTION_SECRET` 用于加密管理员可随时查看的 OpenAPI Key，首次上线后必须稳定保存；不能直接更换或删除，否则既有 Key 仍可鉴权但无法在管理页解密查看。

## 标准发布流程

1. 在本地确认改动、测试和构建通过。
2. 提交后执行：

   ```bash
   git push gitlab main
   ```

3. GitLab 默认分支 Pipeline 通过 SSH 登录生产机，在 `/opt/mme_eval` 执行：

   ```bash
   scripts/deploy_release.sh
   ```

4. 发布脚本取得主机锁后执行以下操作：

   1. 获取并校验 Pipeline 指定的不可变 `CI_COMMIT_SHA`，以 detached HEAD 检出该提交；
   2. 判断 Worker 相关代码是否发生变化；
   3. 对 Postgres 执行自校验的 custom-format 发布前备份；
   4. 构建以完整提交 SHA 标记的新 Web（`app`）镜像；
   5. 重建 `app` 容器，并等待数据库、Schema 与临时评测表均通过 `/api/health` 就绪检查；
   6. Worker 代码或锁文件/迁移有变化时才重建 Worker；否则保留正在执行的 Worker；
   7. 等待 Worker 心跳健康检查通过后结束；任一检查失败会自动恢复上一版镜像。

## 当前发布期间的访问表现

当前生产 Nginx 将全部请求转发到单个 `app` 容器的 `127.0.0.1:8000`。因此第 4 步替换 Web 容器时，旧容器停止、新容器尚未完成启动的短暂窗口内，页面和 API 可能返回 **502 Bad Gateway**。

这不会删除数据，也不会使评测或归因任务丢失；新 Web 容器通过健康检查后，访问会自动恢复。遇到 502 时请等待健康检查完成后刷新页面，不要重复发起发布。

> Worker 默认不会随普通前端/API 发布重建；即使 Worker 因代码更新而重启，也会依赖数据库租约和已持久化的 Case 结果继续处理剩余任务。

## 发布后验证

发布完成后至少验证：

```bash
curl -fsS http://127.0.0.1:8000/api/health
docker compose -f docker-compose.yml -f docker-compose.release.yml ps
```

业务侧还应打开 MME 首页和一条正在运行的评测/归因任务，确认页面可访问、进度正常刷新。

如果健康检查失败，发布脚本会输出最近日志并回退到发布前的 app/worker 镜像。数据库采用向前兼容的加法迁移，不随应用镜像自动降级；需要数据恢复时按下文的显式恢复流程操作。

## 数据库备份与恢复

每次发布会自动调用 `scripts/backup_postgres.sh`，默认保存到 `backups/postgres/`，生成 `.dump` 与 `.sha256`，保留 14 天。可通过 `MME_BACKUP_DIR`、`MME_BACKUP_RETENTION_DAYS` 覆盖。

人工备份：

```bash
scripts/backup_postgres.sh
```

恢复属于破坏性维护操作，只能在确认目标绝对路径和校验和后执行：

```bash
MME_CONFIRM_RESTORE=RESTORE scripts/restore_postgres.sh /绝对路径/mme-时间.dump
```

恢复前应进入维护窗口并停止 `app`、`worker`，恢复完成后重新启动并检查 `/api/health` 与 Worker 健康状态。建议定期在隔离环境演练恢复，不能只验证“备份文件存在”。

## 手动发布与 Worker 控制

仅在需要人工发布时登录生产机执行：

```bash
cd /opt/mme_eval
scripts/deploy_release.sh
```

- `DEPLOY_WORKER=1`：强制重建 Worker。适用于 Worker、队列、任务处理或依赖发生变化后。
- `DEPLOY_WORKER=0`：明确保留现有 Worker。适用于只更新页面/API，且不希望打断当前 Worker 进程的情况。

不要手动删除数据库卷、任务表或正在运行的 Worker 容器来“修复”发布问题。

## 502 故障处理

1. 先确认 Pipeline 是否仍在执行，避免与另一个发布并发。
2. 等待 `/api/health` 恢复；新 Web 实例通常需要完成应用初始化后才会接收请求。
3. 若健康检查持续失败，查看 `app` 容器日志，而不是反复刷新浏览器。
4. 发布脚本会优先自动回退上一版镜像；若仍失败，使用日志中记录的 SHA 定位版本，不要用浮动 `main` 猜测生产代码。

## 后续零中断发布方案（待实施）

要消除上述短暂 502，发布流程将升级为蓝绿切换：

1. 在备用端口启动新 Web 实例，并关闭它的调度器，避免与正式实例重复触发定时任务；
2. 新实例通过 `/api/health` 后，Nginx 原子切换到备用端口；
3. 再更新原正式端口的实例并完成健康检查；
4. Nginx 切回正式端口，最后停止备用实例；
5. Worker 仍按现有数据库租约机制独立滚动更新。

在该方案实际启用前，发布仍以本文件“当前发布期间的访问表现”为准，不能承诺页面完全无中断。
