# NetScope

NetScope 是一个网络数据包流转可视化项目，用科幻风格的世界地图界面展示服务端与客户端之间的数据包传输过程。项目采用前后端分离结构：前端负责地图渲染、动画与实时统计，后端提供随机数据包的 mock API，方便演示网络监控、链路状态和协议分布等场景。

## 项目特点

- 世界地图可视化展示网络节点与链路动画
- 区分服务端与客户端节点，并按真实经纬度落点
- 支持 `TCP`、`UDP`、`ICMP` 三种协议的包动画展示
- 通过颜色区分成功、延迟、丢包三种状态
- 自动轮询后端接口，持续生成动态流量效果
- 支持手动点击 `TRANSMIT` 按钮发送本地模拟数据包
- 提供实时统计面板，展示发送量、成功数和丢包率
- 提供最近 30 条流量趋势小图，辅助观察波动情况

## 技术栈

### 前端

- Next.js 16
- React 19
- TypeScript
- ECharts
- echarts-for-react
- Three.js 生态依赖

### 后端

- Python 3.13
- Django 6.0.4
- SQLite

## 界面与交互说明

前端主页面使用世界地图作为可视化载体：

- 菱形发光节点表示服务器
- 圆形节点表示客户端
- 流动的小圆点代表数据包在链路上的传输
- 绿色链路表示成功
- 黄色链路表示高延迟
- 红色链路表示中途丢包
- 协议颜色区分为：
  - `TCP`：青色
  - `UDP`：紫色
  - `ICMP`：白色

页面左下角控制面板提供：

- 实时统计卡片
- 最近 30 条数据的趋势图
- 手动发送数据按钮
- 状态与协议图例说明

## 项目结构

```text
NetScope/
├── backend/          # Django backend
│   ├── config/
│   ├── docs/
│   ├── integrations/
│   ├── traffic/
│   ├── manage.py
│   └── requirements.txt
├── ikuai-sdk/        # Reusable iKuai Python SDK
│   └── ikuai_sdk/
├── frontend/         # Next.js 可视化前端
│   ├── package.json
│   ├── next.config.ts
│   └── src/
│       ├── app/
│       │   ├── layout.tsx
│       │   ├── page.jsx
│       │   └── globals.css
│       └── utils/
│           └── network.js
└── README.md
```

## 本地运行

### 1. 安装依赖

前后端分别安装依赖：

```bash
cd backend
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
cp .env.example .env
```

```bash
cd frontend
npm install
```

### 2. 启动后端

```bash
cd backend
.venv/bin/python manage.py migrate
.venv/bin/python manage.py runserver 0.0.0.0:4000
```

后端默认运行在：

```text
http://localhost:4000
```

### 3. 启动前端

```bash
cd frontend
npm run dev
```

前端默认运行在：

```text
http://localhost:3000
```

启动后，前端会每秒请求一次后端接口 `GET /api/packet`，并把返回的数据包渲染为地图上的动态传输效果。

## 可用脚本

### frontend

```bash
npm run dev
npm run build
npm run start
npm run lint
```

### backend

```bash
.venv/bin/python manage.py migrate
.venv/bin/python manage.py runserver 0.0.0.0:4000
```

## API 说明

### `GET /api/packet`

返回 1 到 3 条随机数据包数据，供前端轮询展示。

返回示例：

```json
[
  {
    "id": "pkt_001",
    "source": {
      "ip": "192.168.1.10",
      "name": "Client (Beijing)",
      "lat": 39.9,
      "lng": 116.4,
      "type": "client"
    },
    "destination": {
      "ip": "8.8.8.8",
      "name": "Server (Silicon Valley)",
      "lat": 27.994110585072477,
      "lng": 120.69934126685061,
      "type": "server"
    },
    "protocol": "TCP",
    "status": "success",
    "payloadSize": 1024,
    "timestamp": 1712450000
  }
]
```

### `GET /api/health`

用于健康检查。

返回示例：

```json
{
  "status": "ok",
  "uptime": 123.456
}
```

### `GET /api/nodes`

返回当前启用的网络节点。

### `GET /api/routes`

返回当前启用的可用链路。

### `POST /api/ikuai/login`

登录 iKuai 面板并返回 `sess_key`、完整 cookies，以及后续调用可直接复用的 `Cookie` 头。

请求示例：

```json
{
  "routerUrl": "http://10.1.1.1",
  "username": "admin",
  "password": "123"
}
```

返回示例：

```json
{
  "loginUrl": "http://10.1.1.1/Action/login",
  "requestMode": "json",
  "requestPayload": {
    "username": "admin",
    "passwd": "202cb962ac59075b964b07152d234b70",
    "pass": "ac59075b964b07150000",
    "remember_password": ""
  },
  "upstreamStatus": 200,
  "upstreamResponse": {
    "Result": 10000,
    "ErrMsg": "Succeess"
  },
  "cookies": {
    "sess_key": "0249f5edebd84e26103c1193a4ede2c8"
  },
  "sess_key": "0249f5edebd84e26103c1193a4ede2c8",
  "cookieHeader": "sess_key=0249f5edebd84e26103c1193a4ede2c8; username=admin; login=1"
}
```

## 当前内置节点

项目当前内置了一组示例节点：

- 1 个服务器节点
- 3 个客户端节点
- 支持的链路规则为：
  - 服务器 <-> 客户端
  - 服务器 <-> 服务器
  - 不支持 客户端 <-> 客户端

这些数据由 Django 模型和初始迁移提供：

- `backend/traffic/models.py`
- `backend/traffic/migrations/0002_seed_network_data.py`

## 开发说明

- 前端页面核心入口为 `frontend/src/app/page.jsx`
- 样式定义位于 `frontend/src/app/globals.css`
- API 设计文档见 `backend/docs/api-design.md`
- 数据库设计文档见 `backend/docs/database-design.md`
- 后端使用 Django + SQLite，随机包生成逻辑位于 `backend/traffic/services.py`
- iKuai 登录 SDK 位于 `ikuai-sdk/ikuai_sdk/`，Django 集成层在 `backend/integrations/services.py`
- 运行环境变量示例见 `backend/.env.example`，代理或外网域名访问时需配置 `DJANGO_ALLOWED_HOSTS`

## 后续可扩展方向

- 接入真实设备或日志系统作为数据源
- 增加更多服务器和客户端节点
- 增加筛选条件，如协议、地区、状态
- 支持历史回放与时间轴控制
- 增加更完整的告警、吞吐量和延迟监控面板
- 引入 WebSocket 代替轮询，实现更实时的数据推送

## 适用场景

- 网络流量演示
- 安全可视化大屏
- 教学或汇报展示
- 网络监控原型验证

## License

如需开源发布，建议补充具体许可证信息，例如 `MIT`。
