# 水电工上门维修小程序（个人版）

> 前后端分离的上门维修预约系统：微信小程序客户端 + FastAPI 后端 + SQLite。
> 面向个人水电工使用——客户微信授权登录后下单，师傅在同一小程序内接单、管理客户、统计收入。

## 技术栈

| 层 | 技术 | 说明 |
|---|---|---|
| 前端 | 微信小程序原生框架（WXML/WXSS/JS） | 零第三方框架，客户端与师傅端同端共存 |
| 后端 | Python 3.13 + FastAPI + Uvicorn | 单体模块化，自带 OpenAPI 文档（/docs） |
| 数据 | SQLite + SQLAlchemy ORM | 零运维；`DATA_DIR` 支持数据目录外置 |
| 认证 | 微信 code2session + HMAC 签名 token | 客户 token 无状态（重启不失效）；师傅端密码登录 |
| 部署 | Docker / docker-compose | 数据卷挂载宿主机，重建容器不丢数据 |

## 图片
<img width="433" height="459" alt="image" src="https://github.com/user-attachments/assets/a0f3acf0-b469-4bb5-b870-8d427c4b9b69" />
<img width="455" height="468" alt="image" src="https://github.com/user-attachments/assets/89e07f76-e2db-4d3f-8d02-f7ab2dc6483f" />

## 架构

```
┌─────────────────────────────────────────────┐
│  微信小程序（原生框架）                       │
│  ├── 客户端：登录绑定 / 下单 / 我的订单       │
│  └── 师傅端：订单管理 / 客户后台 / 收入统计   │
└──────────────────┬──────────────────────────┘
                   │ HTTP / JSON（wx.request）
┌──────────────────▼──────────────────────────┐
│  FastAPI 后端（20 个路由）                   │
│  ├── 认证模块：微信登录 / 手机号绑定 / 鉴权  │
│  ├── 业务模块：订单状态机 / 统计 / 客户聚合  │
│  └── 基础设施：ORM / CORS / 静态文件 / 上传  │
└────────┬───────────────────────┬────────────┘
         │ SQLAlchemy            │ 文件写入
┌────────▼─────────┐   ┌─────────▼──────────┐
│  SQLite          │   │  uploads/ 图片目录  │
│  users/orders/   │   │  （StaticFiles）    │
│  services        │   │                    │
└──────────────────┘   └────────────────────┘
```

## 功能特性

**客户端**
- 微信一键登录（授权微信身份）+ 绑定手机号，登录后才能下单/查单
- 服务项目九宫格、8 类常见水电维修项目价格表
- 表单下单：姓名、电话、地址、服务项目、期望时间、故障描述、最多 3 张故障照片
- 我的订单：自动展示全部订单、详情查看、一键电话联系师傅、下拉刷新

**师傅端（首页隐藏入口进入）**
- 密码登录（token 有效期 7 天）
- 订单管理：状态筛选、接单/开始维修/完成收费/取消、一键拨打客户电话
- 客户信息后台：按手机号聚合（订单数、完成数、累计消费、最近下单、常用地址、微信注册标记）、搜索、展开历史订单
- 月度收入统计：完成单数、总收入、状态分布、收入条形图

**订单状态机**

```
pending(待接单) → confirmed(已预约) → repairing(维修中) → completed(已完成)
任意未完成状态 → cancelled(已取消)
```

## 快速开始

### 1. 启动后端

```bash
cd backend
pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 8000
```

常用环境变量：

```bash
MASTER_PASSWORD=师傅端密码      # 默认 123456，务必修改
WX_APPID=小程序AppID WX_SECRET=小程序AppSecret   # 不配置则走开发模式
DATA_DIR=/path/to/data          # 数据库与图片目录（默认 backend/ 下）
```

> 微信登录：不配置 `WX_APPID/WX_SECRET` 也能跑（开发模式，按设备生成稳定身份）；
> 正式使用在 [微信公众平台](https://mp.weixin.qq.com) → 开发管理 → 开发设置获取。
> 个人主体小程序无法使用官方「手机号快速验证」组件（需企业认证），手机号采用登录后手动绑定，一次绑定长期有效。

接口文档：http://127.0.0.1:8000/docs

### 2. 运行小程序

1. 微信开发者工具 → 导入项目 → 选择 `miniprogram/` 目录
2. 修改 `utils/api.js` 第 2 行 `BASE_URL`：
   - 模拟器：`http://127.0.0.1:8000`
   - 真机预览：电脑局域网 IP，如 `http://192.168.1.100:8000`
3. 详情 → 本地设置 → 勾选「不校验合法域名」
4. 修改 `pages/order-detail/order-detail.js` 中 `callMaster` 的电话号码为师傅本人号码

## Docker 部署

```bash
docker compose up -d --build        # http://服务器IP:8000
```

数据库与上传图片持久化到宿主机 `./data/`。更多方式（systemd 直跑、Nginx + HTTPS）见 [DEPLOY.md](./DEPLOY.md)。

## API 一览

| 方法 | 路径 | 说明 | 认证 |
|---|---|---|---|
| GET | /api/services | 服务项目列表 | 否 |
| POST | /api/auth/login | 微信登录（code 换 openid，自动注册） | 否 |
| POST | /api/auth/bind-phone | 绑定手机号/称呼 | 客户 |
| GET | /api/auth/me | 当前登录客户信息 | 客户 |
| POST | /api/orders | 客户下单 | 客户 |
| GET | /api/orders/my | 我的订单（登录态） | 客户 |
| GET | /api/orders?phone= | 按手机号查订单 | 否 |
| GET | /api/orders/{id} | 订单详情 | 否 |
| POST | /api/upload | 上传故障照片 | 否 |
| POST | /api/master/login | 师傅登录 | 否 |
| GET | /api/master/orders?status= | 全部订单（可筛选） | 师傅 |
| GET | /api/master/customers?q= | 客户信息管理（聚合统计） | 师傅 |
| POST | /api/orders/{id}/status | 更新状态/收费 | 师傅 |
| GET | /api/master/stats?month= | 月度收入统计 | 师傅 |

## 目录结构

```
repair-app/
├── backend/               # FastAPI 后端
│   ├── main.py            # 全部接口（认证/订单/客户/统计/上传）
│   ├── models.py          # ORM 模型 + 种子数据 + 旧库自动迁移
│   ├── requirements.txt
│   └── repair.db          # SQLite（首次运行自动创建）
├── miniprogram/           # 微信小程序（开发者工具导入此目录）
│   ├── app.js / app.json / app.wxss
│   ├── utils/api.js       # 请求封装（双 token + 上传重试）
│   └── pages/             # 10 个页面（客户端 7 + 师傅端 3）
├── Dockerfile
├── docker-compose.yml
├── DEPLOY.md              # 部署指南
└── README.md
```

## 已知限制（个人使用场景下的取舍）

- SQLite 单写锁，高并发场景建议迁移 PostgreSQL/MySQL（ORM 层已就位）
- 客户端状态同步为 onShow + 下拉刷新的轮询式方案，真推送需 WebSocket
- 师傅端 token 内存存储，后端重启需重新登录
- 正式对外上线需已备案域名 + HTTPS
