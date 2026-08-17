# MME 生产发布说明

本文说明 MME 的正式发布入口、当前实际发布行为、验证和回滚方式。生产代码只从 GitLab 发布。

## 发布原则

- 唯一生产代码源：`git@gitlab.soundws.com:cx/cx-mme.git`。
- 只允许推送 `gitlab/main`；`origin`（GitHub）不参与生产发布。
- GitLab Pipeline 使用 `mme-production` 资源锁，同一时间只允许一个发布进行。
- 发布不会重建数据库和数据卷。评测、重新评测和归因任务均以数据库中的任务记录与租约为准，Worker 重启后会继续领取未完成工作。

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

   1. `git pull --ff-only` 拉取 GitLab 的最新 `main`；
   2. 判断 Worker 相关代码是否发生变化；
   3. 构建新的 Web（`app`）镜像；
   4. 重建 `app` 容器；
   5. 轮询 `/api/health`，确认 Web 服务恢复；
   6. Worker 代码有变化时才重建 Worker；否则保留正在执行的 Worker；
   7. 确认 Worker 运行后，发布结束。

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

如果健康检查失败，发布脚本会输出 `app` 最近日志并以失败退出；不要继续执行后续发布。应先根据容器日志定位启动失败原因。

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
4. 若仅 Web 发布失败且旧镜像仍可用，可回退到上一个 GitLab 提交后重新执行发布；数据库不回滚，任务记录保留。

## 后续零中断发布方案（待实施）

要消除上述短暂 502，发布流程将升级为蓝绿切换：

1. 在备用端口启动新 Web 实例，并关闭它的调度器，避免与正式实例重复触发定时任务；
2. 新实例通过 `/api/health` 后，Nginx 原子切换到备用端口；
3. 再更新原正式端口的实例并完成健康检查；
4. Nginx 切回正式端口，最后停止备用实例；
5. Worker 仍按现有数据库租约机制独立滚动更新。

在该方案实际启用前，发布仍以本文件“当前发布期间的访问表现”为准，不能承诺页面完全无中断。
