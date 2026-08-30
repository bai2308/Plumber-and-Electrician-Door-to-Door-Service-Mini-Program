# 水电工上门维修小程序 — 服务器部署指南

## 方式一：Docker 部署（推荐）

```bash
# 1. 上传 repair-app.zip 到服务器并解压
unzip repair-app.zip && cd repair-app

# 2. 启动（首次会自动构建镜像，数据持久化在 ./data）
docker compose up -d --build

# 3. 查看状态
docker compose ps && docker compose logs -f
```

- 服务地址：`http://服务器IP:8000`
- 修改密码：编辑 `docker-compose.yml` 中 `MASTER_PASSWORD` 环境变量后 `docker compose up -d` 重启
- **微信正式登录**：编辑 `docker-compose.yml` 中 `WX_APPID` / `WX_SECRET`（微信公众平台 → 开发设置），并设置 `AUTH_SECRET`（任意随机长字符串，用于签发客户登录 token，更换后所有客户端需重新登录）
- 数据库和上传图片保存在宿主机 `./data/` 目录，重建容器不丢数据

## 方式二：直接运行（服务器已装 Python 3.10+）

```bash
cd repair-app/backend
python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt
MASTER_PASSWORD=你的密码 uvicorn main:app --host 0.0.0.0 --port 8000
```

生产建议用 systemd 常驻：

```ini
# /etc/systemd/system/repair.service
[Unit]
Description=Repair Service API
After=network.target

[Service]
WorkingDirectory=/opt/repair-app/backend
ExecStart=/opt/repair-app/backend/venv/bin/uvicorn main:app --host 0.0.0.0 --port 8000
Environment=MASTER_PASSWORD=你的密码
Restart=always

[Install]
WantedBy=multi-user.target
```

```bash
systemctl enable --now repair
```

## 方式三：Nginx 反代 + HTTPS（可选）

```nginx
server {
    listen 443 ssl;
    server_name your.domain.com;
    ssl_certificate     /path/fullchain.pem;
    ssl_certificate_key /path/privkey.pem;

    client_max_body_size 10m;   # 照片上传

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

## 小程序端上线前修改

1. `miniprogram/utils/api.js` 的 `BASE_URL` 改为 `https://你的域名`（已配 HTTPS）
2. 微信公众平台 → 开发管理 → 服务器域名 → 添加 `https://你的域名` 到 request/uploadFile 合法域名
   - 个人主体小程序可以配置 20 个域名，但**上线正式版必须走已备案域名 + HTTPS**
   - 仅自己体验版使用：开发者工具勾选「不校验合法域名」+ 手机上打开开发调试即可跳过校验
3. `miniprogram/pages/order-detail/order-detail.js` 中师傅电话号码
4. `miniprogram/project.config.json` 的 `appid` 换成你自己的（微信公众平台注册获取）

## 数据备份

```bash
# SQLite 数据库 + 上传照片都在 data/ 目录
tar czf backup-$(date +%F).tar.gz data/
```
