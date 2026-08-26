# NetScope · Global Network Intelligence Center

全球网络智能监控中心 —— 一个基于 **Django + Next.js** 的实时网络态势感知系统。

通过可视化方式实时展示服务器的网络流量、连接、数据包、NAT、IP、端口、协议，以及与全球各地节点的通信情况。

![NetScope 全球网络智能中心](doc/img/cover.png)

```text
iKuai Router
        │
        ▼
   Django Backend  ──▶  REST JSON API
        │
        ▼
   Next.js Frontend（轮询 → Buffer 批量 → Adapter → Zustand Store）
        │
        ▼
GLOBAL / CHINA / LAN 三场景实时大屏
```

## 核心特性

- **三场景地图**：`GLOBAL` 世界地图、`CHINA` 中国地图、`LAN` 内网设备拓扑，Canvas 自研渲染引擎平滑切换
- **方向语义**：`outbound`（青色）/ `inbound`(紫色) / `internal`（绿色），严格信任后端判定结果
- **服务器核心节点**：发光旋转环 + 脉冲 + 雷达扫描的 CYBER CORE 视觉
- **真实数据驱动**：只消费 iKuai 路由器的真实终端、连接明细与 NAT 端口映射；未连接时空状态展示并持续自动重连，绝不伪造流量
- **实时统计聚合**：连接计数、带宽序列、丢包率、平均延迟、区域延迟热力图
- **排行榜**：国家 / IP / 端口 / 应用全部由真实数据动态生成，不预设固定值
- **NAT Pipeline 可视化**：公网来源 → NAT → 内网目标的完整链路展示
- **HUD 风格交互**：启动动画、事件流、连接详情、数据流 Hover Tooltip

## 技术栈

| 层 | 技术 |
| --- | --- |
| 前端 | Next.js 15 · React 19 · TypeScript（strict）· Tailwind CSS 4 · Zustand |
| 地图渲染 | 自研 Canvas 渲染引擎（无重型地图依赖）· GeoJSON（`public/maps/`） |
| 后端 | Python · Django 5.2（轻量 JSON API，运行态数据全内存） |
| 数据源 | `sdk/ikuai_sdk`（iKuai 路由器 SDK），仅真实数据 |

## 项目结构

```text
NetScope/
├── AGENTS.md               # 项目规范与架构设计文档
├── doc/                    # 文档图片等资源
├── sdk/
│   ├── README.md           # iKuai SDK 说明
│   ├── demo.py
│   └── ikuai_sdk/          # iKuai 面板登录 / Action/call / 终端列表 SDK
├── backend/
│   ├── manage.py
│   ├── config/             # Django 配置（最小化，无 admin/session）
│   └── traffic/
│       ├── hub.py          # TrafficHub 全局状态中枢（线程安全、环形事件日志）
│       ├── ikuai.py        # iKuai 轮询器（终端列表 + 连接明细 diff 发射事件）
│       ├── packets.py      # 标准化数据包构建
│       ├── stats.py        # 实时统计聚合器
│       ├── geo.py          # GeoIP 定位 / 私有 IP 判断
│       ├── views.py        # JSON API
│       └── urls.py
└── frontend/
    ├── public/maps/        # world.json / china.json 地图数据
    └── src/
        ├── app/            # Next.js App Router 入口
        ├── components/
        │   ├── dashboard/  # Dashboard 容器
        │   ├── hud/        # Header / BootSequence / SceneSwitcher 等 HUD 元素
        │   ├── map/        # MapStage + renderEngine（Canvas 渲染引擎）
        │   ├── panels/     # Metrics / Monitor / Radar / Rankings 面板
        │   ├── charts/     # 带宽趋势图
        │   ├── details/    # ConnectionDetails（含 NAT Pipeline）
        │   └── events/     # EventStream 实时事件流
        ├── hooks/          # useNetworkStream / useWindowedFlows
        ├── lib/
        │   ├── api/        # API 客户端（容错，失败返回 null 降级）
        │   ├── adapters/   # 后端原始数据 → NetworkFlow 归一化适配层
        │   └── network/    # 投影 / 私有 IP 判断 / 国家名映射
        ├── store/          # networkStore（Zustand，上限 5000 条自动淘汰）
        └── types/          # 统一类型定义
```

## 快速开始

### 后端（Django）

```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python manage.py runserver 0.0.0.0:8000
```

启动后访问 `http://localhost:8000/api/health` 应返回 `{"status": "ok"}`。

### 前端（Next.js）

```bash
cd frontend
npm install
npm run dev
```

打开 `http://localhost:3000` 即可看到监控大屏。

### 接入真实 iKuai 路由器

推荐在 `backend/.env`（已被 git 忽略）中配置，服务启动即自动连接：

```bash
# 主地址建议用内网面板（无 WAF 拦截）
NETSCOPE_IKUAI_URL=http://10.0.1.1:6301
# 主地址被 WAF 拦截 / 不可达时自动轮换到备用地址
NETSCOPE_IKUAI_FALLBACK_URL=https://ikuai.elsworld.cn:8443
NETSCOPE_IKUAI_USERNAME=keshihua
NETSCOPE_IKUAI_PASSWORD=your-password
```

三项齐全时 Django 启动后自动登录路由器；连接失败 API 返回空状态，后台每 15 秒重试直到成功。
系统只消费真实网络数据，无任何内置模拟流量。登录遭遇 iKuai 防暴力 WAF 挑战时 SDK 会自动携带挑战 cookie
重试；主地址连续失败 4 次自动切换备用地址。也可以不配置环境变量、运行时手动连接：

```bash
curl -X POST http://localhost:8000/api/ikuai/connect \
  -H "Content-Type: application/json" \
  -d '{"routerUrl": "http://192.168.1.1", "username": "admin", "password": "your-password"}'
```

连接成功后开始拉取真实终端与连接数据（2s 轮询），带宽与 CPU 负载同样实时采集。

## 环境变量

### 后端

| 变量 | 默认值 | 说明 |
| --- | --- | --- |
| `DJANGO_SECRET_KEY` | dev-only 占位 | 生产环境必须修改 |
| `DJANGO_DEBUG` | `true` | 生产环境设为 `false` |
| `DJANGO_ALLOWED_HOSTS` | `localhost,127.0.0.1,0.0.0.0` | 允许的主机名 |
| `NETSCOPE_GATEWAY_LAT` / `NETSCOPE_GATEWAY_LNG` | `39.9042` / `116.4074` | 网关地理位置（内网节点聚簇中心） |
| `NETSCOPE_IKUAI_URL` | 空 | iKuai 面板地址，与下面两项同时配置后启动即自动连接 |
| `NETSCOPE_IKUAI_FALLBACK_URL` | 空 | 备用面板地址（如内网 `http://10.0.1.1:6301`），主地址被 WAF 拦截/不可达时自动轮换 |
| `NETSCOPE_IKUAI_USERNAME` | 空 | iKuai 用户名 |
| `NETSCOPE_IKUAI_PASSWORD` | 空 | iKuai 密码 |

> 上下行带宽取自 iKuai `monitor_iface` 接口实时速率（`iface_stream` 的 WAN 口汇总，
> 单位 B/s），是路由器自身的权威口径；连接级流量差分仅在其失效时作为兜底。

### 前端

| 变量 | 默认值 | 说明 |
| --- | --- | --- |
| `NEXT_PUBLIC_API_URL` | `http://localhost:8000` | Django API 地址 |

## API 一览

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/api/health` | 健康检查 |
| GET | `/api/packets?since=<seq>` | 增量数据包事件 |
| GET | `/api/history?minutes=10` | 历史事件（时间轴回放） |
| GET | `/api/devices` | 内网设备列表 |
| GET | `/api/nodes` | 公网节点列表（含经纬度） |
| GET | `/api/stats` | 实时统计快照（连接 / 方向 / 协议 / 应用 / 带宽 / 延迟热力图） |
| GET | `/api/mode` | 当前数据源模式与运行状态 |
| POST | `/api/ikuai/connect` | 连接 iKuai 路由器并切换真实数据源 |

## 数据链路设计

前端不直接消费后端原始 JSON，而是经过统一适配层归一化为 `NetworkFlow` 结构：

```text
Django API ──poll──▶ Buffer ──80ms 批量──▶ Adapter ──▶ Zustand Store ──▶ Canvas / React
```

- 数据包轮询 900ms（失败指数退避至 6s）、统计 2s、设备/节点 5s
- 每批数据一次性提交 store，避免逐条触发 React 重渲染
- 内存上限：最近 5000 条事件，超出自动淘汰最旧数据
- 所有请求容错：单条异常数据不会导致页面崩溃

详细设计规范见 [AGENTS.md](AGENTS.md)，SDK 使用说明见 [sdk/README.md](sdk/README.md)。

## Roadmap

- [ ] WebSocket 实时推送（Django Channels + Redis 替代轮询传输）
- [ ] PostgreSQL 历史数据持久化
- [ ] 异常检测 / 威胁监控（当前未伪造攻击数据）
- [ ] Docker Compose 一键部署 + Nginx 生产配置
