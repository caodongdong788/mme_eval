# MME 生产 Nginx 配置

云主机在 Docker `app` 前加 Nginx 时，用本目录模板实现 **SPA `try_files` 双保险**（与容器内 `server/spa_static.py` 并存）。

## 架构

```text
浏览器 → Nginx :443
           ├─ /api/*     → proxy 127.0.0.1:8000（FastAPI）
           ├─ /assets/*  → 磁盘静态（try_files）
           └─ /*         → try_files $uri $uri/ /index.html
```

`frontend/dist` 需在 Nginx 可读路径（见下文同步）。

## 1. 同步前端静态文件

在**项目根目录**执行（`docker compose` 已 build 且 `app` 在跑）：

```bash
sudo scripts/sync_nginx_static.sh /var/www/mme/frontend/dist
```

或在本机构建后拷贝：

```bash
cd frontend && npm ci && npm run build
sudo mkdir -p /var/www/mme/frontend
sudo cp -r dist /var/www/mme/frontend/
```

**每次** `docker compose up -d --build` 更新前端后，应重新同步 `dist`（仅 API 变更可跳过）。

## 2. 安装配置

```bash
# 编辑 server_name、root 路径（若不用默认 /var/www/mme/frontend/dist）
sudo cp deploy/nginx/mme.conf /etc/nginx/sites-available/mme
sudo nano /etc/nginx/sites-available/mme

sudo ln -sf /etc/nginx/sites-available/mme /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
```

## 3. HTTPS（Let's Encrypt）

```bash
sudo apt install -y certbot python3-certbot-nginx
sudo certbot --nginx -d eval.example.com
```

证书续期：`certbot renew`（通常已配 cron）。

## 4. 与 `.env` 对齐

| 变量 | 示例 |
|------|------|
| `FRONTEND_URL` | `https://eval.example.com` |
| `FEISHU_REDIRECT_URI` | `https://eval.example.com/api/auth/feishu/callback` |

飞书开发者后台重定向 URL 须与上表完全一致。

## 5. 验证

```bash
curl -sI https://eval.example.com/runs | head -1          # 期望 HTTP/2 200
curl -sI https://eval.example.com/api/health | head -1    # 期望 200
```

直接访问 `/runs`、刷新评测详情页均应正常（Nginx `try_files` + 后端 SPA 回退双保险）。
