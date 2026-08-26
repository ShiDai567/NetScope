# NetScope 后端设计文档

# GLOBAL NETWORK INTELLIGENCE CENTER — Backend Design

> 版本：v1.0（2026-08-26）
> 范围：Django 后端整体架构、数据采集、数据标准化、Redis 实时层、数据库、REST API、WebSocket 协议、安全与部署。
> 上游规范：`/AGENTS.md`（下文以 §N 引用其章节）。
> 关联代码：`frontend/src/lib/api/client.ts`（前端既有 API 契约）、`sdk/ikuai_sdk/`（iKuai 数据源 SDK）、`sdk/demo_result.json`（真实数据样本）。

---

## 目录

1. [设计目标与原则](#1-设计目标与原则)
2. [总体架构](#2-总体架构)
3. [技术栈与依赖](#3-技术栈与依赖)
4. [后端目录结构](#4-后端目录结构)
5. [核心模块设计](#5-核心模块设计)
6. [方向判定规则（权威实现）](#6-方向判定规则权威实现)
7. [Geo 地理服务](#7-geo-地理服务)
8. [Redis 实时数据层](#8-redis-实时数据层)
9. [数据库设计](#9-数据库设计)
10. [REST API 设计](#10-rest-api-设计)
11. [WebSocket 设计](#11-websocket-设计)
12. [Mock 模式设计](#12-mock-模式设计)
13. [安全设计](#13-安全设计)
14. [性能与容量规划](#14-性能与容量规划)
15. [错误处理与日志](#15-错误处理与日志)
16. [配置项清单](#16-配置项清单)
17. [测试策略](#17-测试策略)
18. [部署方案](#18-部署方案)
19. [开发里程碑](#19-开发里程碑)
20. [附录](#20-附录)

---

## 1. 设计目标与原则

从 AGENTS.md 提炼出后端必须满足的硬性约束：

| # | 原则 | 来源 |
|---|------|------|
| P1 | **真实数据**：所有流量来自 iKuai 路由器，禁止随机伪造 IP / 国家 / 流量 | §79 |
| P2 | **方向权威在后端**：`outbound / inbound / internal` 由 Django 判定，前端不得重复猜测 | §19 |
| P3 | **私网 IP 永不做公网 GeoIP**：10/8、172.16/12、192.168/16 只进 LAN 场景 | §23 |
| P4 | **Adapter 归一层**：iKuai 原始字段 → 标准化 Packet，任何一条脏数据不得拖垮系统 | §17、§61 |
| P5 | **Redis 承载实时热数据**，数据库只存历史快照，不过度建模 | §64 |
| P6 | **批量广播**：WebSocket 按 200–500ms 批量推送，不允许逐条刷 | §34 |
| P7 | **有限缓存**：事件环形缓冲有上限，超限淘汰 | §35 |
| P8 | **Mock 与 Real 同构**：Mock 数据走完全相同的 Adapter → Store 管线，禁止第二套 UI 数据 | §67 |
| P9 | **可扩展协议**：WS 消息 `{type, timestamp, data}` 信封，新增 `alert` 等类型无需改架构 | §66 |
| P10 | **前后端契约稳定**：前端已实现的 `/api/*` 契约必须原样兼容（见 §10.3） | 本文档 |

---

## 2. 总体架构

### 2.1 数据流总览

```text
┌─────────────────────────────────────────────────────────────────────────┐
│                            iKuai Router                                 │
│   /Action/login · monitor_lanip(终端+连接) · monitor_system · WAN 信息    │
└───────────────┬─────────────────────────────────────────────────────────┘
                │ HTTP (sess_key Cookie)
                ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                     Collector Worker（独立进程）                          │
│                                                                         │
│  SessionManager ──▶ IKuaiGateway(封装 sdk) ──▶ PollScheduler(asyncio)    │
│                                    │                                    │
│                    终端列表轮询 ────┤──── 系统指标轮询                     │
│                    连接详询轮询 ────┘──── WAN 出口检测                      │
│                                    │                                    │
│                                    ▼                                    │
│                        Adapter / Normalizer                             │
│              （方向判定 · 私网识别 · 字段清洗 · NAT 解析）                   │
│                                    │                                    │
│              GeoService ◀──────────┤（公网 IP 补充 lat/lng/country/city） │
│                                    │                                    │
│            ┌───────────────────────┼──────────────────────┐             │
│            ▼                       ▼                      ▼             │
│      RedisStore(热)         Aggregator(滚动统计)        EventBus          │
└──────┬───────────────────────────┬──────────────────────┬───────────────┘
       │                           │                      │ group_send
       ▼                           ▼                      ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                        Web 层（ASGI 进程）                                │
│   DRF REST (/api/*)                Django Channels (/ws/network/)        │
└──────┬──────────────────────────────────────────────┬───────────────────┘
       │ JSON                                         │ WebSocket
       ▼                                              ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                              Next.js 前端                                 │
│     api client + adapter + zustand store + 地图 / 面板可视化               │
└─────────────────────────────────────────────────────────────────────────┘

冷路径：Aggregator ──每分钟──▶ PostgreSQL / SQLite（TrafficSnapshot 等）
```

### 2.2 进程拓扑

| 进程 | 启动方式 | 职责 |
|------|----------|------|
| `asgi-web` | `daphne -b 0.0.0.0 -p 8000 config.asgi:application` | REST API + WebSocket（Channels） |
| `collector` | `python manage.py collect_network` | iKuai 轮询、归一、写 Redis、聚合、广播 |
| `redis` | redis-server 7.x | Channel Layer + 实时热数据 + Geo 缓存 |
| `postgres`（可选） | PostgreSQL 15+ | 历史 rollup；开发期可用 SQLite |

> 开发期允许单进程模式：`RUN_COLLECTOR_IN_PROCESS=1` 时由 Django 启动钩子在
> `runserver` 内拉起 collector 线程，便于快速调试（见 §5.2.4）。生产禁用。

---

## 3. 技术栈与依赖

| 组件 | 选型 | 说明 |
|------|------|------|
| 语言 | Python 3.12+ | 类型注解全量开启（mypy strict 可选） |
| Web 框架 | Django 5.x | |
| REST | djangorestframework 3.15+ | 只读 API |
| 实时通道 | channels 4.x + channels-redis 4.x | WS 推送 |
| ASGI server | daphne（或 uvicorn） | 生产不使用 gunicorn 同步 worker |
| 缓存/实时存储 | redis-py 5.x | 自建轻量 `RedisStore`，避免引入重型框架 |
| 数据库 | SQLite（dev）/ PostgreSQL 15（prod） | 仅存历史数据 |
| GeoIP | MaxMind GeoLite2-City（主）+ ip2region xdb（中国增强，可选） | 服务端统一处理（§24） |
| Schema 文档 | drf-spectacular | 导出 OpenAPI 3 |
| 配置 | django-environ | 全部配置走 `.env` |
| 日志 | structlog（JSON 输出可选） | 结构化日志 |
| 测试 | pytest + pytest-django + pytest-asyncio | fixture 复用 `sdk/demo_result.json` |
| 格式化 | ruff + ruff-format | lint + format 一体 |

`requirements.txt`（建议锁定大版本）：

```text
Django>=5.0,<5.2
djangorestframework>=3.15
channels>=4.1
channels-redis>=4.2
daphne>=4.1
django-environ>=0.11
redis>=5.0
drf-spectacular>=0.27
structlog>=24.1
psycopg[binary]>=3.1        # prod
geoip2>=4.8                  # GeoLite2
pytest>=8; pytest-django>=4.8; pytest-asyncio>=0.23
ruff>=0.5
```

---

## 4. 后端目录结构

在 AGENTS.md §62 建议的基础上细化：

```text
backend/
├── manage.py
├── requirements.txt / requirements-dev.txt
├── .env.example
├── pyproject.toml                  # ruff / mypy / pytest 配置
│
├── config/
│   ├── settings/
│   │   ├── base.py                 # 公共配置
│   │   ├── dev.py                  # DEBUG=True, SQLite, 单进程 collector 允许
│   │   └── prod.py                 # PostgreSQL, 安全 Cookie, 关闭 DEBUG
│   ├── urls.py                     # /api/ + /api/schema
│   ├── asgi.py                     # ProtocolTypeRouter + AuthMiddlewareStack
│   ├── routing.py                  # ws 路由注册
│   └── wsgi.py
│
├── core/                           # 跨应用基础设施
│   ├── redis_store.py              # RedisStore：全部 key 读写集中于此
│   ├── event_bus.py                # EventBus：向 channel layer 广播
│   ├── geo/                        # GeoService
│   │   ├── provider.py             # GeoProvider 抽象接口
│   │   ├── maxmind_provider.py     # GeoLite2-City 实现
│   │   ├── ip2region_provider.py   # 中国城市增强（可选）
│   │   ├── manual_overrides.py     # 手工覆盖表（env/json 加载）
│   │   └── service.py              # 缓存编排（Redis TTL → DB → Provider）
│   ├── lan_layout.py               # 私网设备环形布局（伪坐标）
│   └── utils/
│       ├── network.py              # is_private_ip / ip_to_int / conn_key
│       └── timeutil.py             # 统一秒级时间戳
│
├── network/                        # 采集 + 实时域
│   ├── models.py                   # FlowRecord / SystemEvent（见 §9）
│   ├── adapters/
│   │   ├── ikuaipacket.py          # iKuai conn 行 → 标准 Packet dict
│   │   ├── direction.py            # 方向判定规则（§6，纯函数可单测）
│   │   ├── device.py               # 终端列表 → Device dict
│   │   └── systeminfo.py           # monitor_system → 系统指标
│   ├── services/
│   │   ├── packet_service.py       # seq 分配、环形缓冲写入、去重
│   │   ├── connection_service.py   # 连接登记/更新/关闭、速率差分
│   │   ├── device_service.py       # 设备表维护、ring_index 分配
│   │   └── status_service.py       # 网关位置、WAN IP、iKuai 在线状态
│   ├── management/commands/
│   │   ├── collect_network.py      # ★ collector 主进程入口
│   │   └── prune_history.py        # 历史数据清理（cron/beat 调用）
│   ├── consumers.py                # NetworkConsumer（§11）
│   ├── routing.py                  # ws/network/ → consumer
│   ├── serializers.py              # DRF serializer（对外 JSON 契约）
│   └── views.py                    # REST 视图（薄壳，逻辑在 services）
│
├── analytics/                      # 统计聚合域
│   ├── aggregators.py              # 滚动窗口计数器（protocols/apps/ports/ips/countries）
│   ├── bandwidth.py                # 带宽序列计算与平滑
│   ├── models.py                   # TrafficSnapshot（历史 rollup）
│   ├── services.py                 # NetworkStatisticsService：组装 /api/stats
│   └── serializers.py
│
├── datasource/
│   ├── ikuai/
│   │   ├── gateway.py              # 封装 sdk.IKuaiClient：登录态管理 + func 调用
│   │   ├── session_manager.py      # sess_key 生命周期、401 自动重登、退避
│   │   ├── scheduler.py            # asyncio 轮询调度（分频、错峰）
│   │   └── funcs.py                # iKuai func_name/action/payload 常量表
│   └── mock/
│       ├── generator.py            # Mock 包生成器（严格模拟 iKuai 行结构）
│       └── scenarios.py            # 场景剧本（outbound/inbound/internal/nat）
│
└── tests/
    ├── fixtures/ikuai_demo.json    # 由 sdk/demo_result.json 裁剪生成
    ├── test_adapters_direction.py
    ├── test_adapters_packet.py     # 含脏数据模糊测试
    ├── test_geo_service.py
    ├── test_stats_service.py
    ├── test_api_endpoints.py
    └── test_ws_consumer.py
```

分层依赖方向（禁止反向依赖）：

```text
datasource ──▶ network.adapters ──▶ network.services ──▶ core.redis_store / analytics
                                   network.views/consumers ──▶ services（views 不写业务）
```

---

## 5. 核心模块设计

### 5.1 iKuai 数据源层（datasource）

#### 5.1.1 iKuai 接口映射表（funcs.py）

SDK 已提供登录、终端列表、单终端连接详询能力。其余指标通过通用 `call()` 实现，
func 名称集中在常量表中，便于不同固件版本微调：

| 用途 | func_name | action | 关键 param | SDK 方法 | 周期（默认） |
|------|-----------|--------|------------|----------|--------------|
| 登录 | — | — | MD5 密码 | `login()` | 过期时 |
| 在线终端列表 | `monitor_lanip` | `show` | `TYPE=data,total` | `get_terminal_list()` | 10s |
| 单终端连接详询 | `monitor_lanip` | `show` | `TYPE=conn,conn_num&ip=<ip>` | `get_terminal_connection_details()` | 5s（分终端错峰） |
| 系统负载 | `monitor_system` | `show` | — | `call()` | 5s |
| WAN 口信息/流量 | `monitor_wan`* | `show` | — | `call()` | 10s |
| 接口实时速率（若固件支持） | `monitor_interface_stream`* | — | — | `call()` | 5s |

> \* 带 `monitor_` 前缀的非 SDK 内置接口在不同 iKuai 固件上命名可能不同。
> `funcs.py` 中每个 payload 都做成可被 env 覆盖的常量；首次联调以
> `sdk/demo.py` 实测结果为准并回填。无法获取的能力优雅降级为 `null`
> （如延迟数据），前端已按可缺失设计。

#### 5.1.2 SessionManager

```text
职责：
  - 持有 {router_url, username, cookie_header}
  - call() 收到 Result=10001 / 401 时自动重新 login() 并重放一次请求
  - 连续失败 ≥3 次 → 进入退避（5s→30s），同时向 EventBus 发布 status 事件：
      {"state": "ikuai_disconnected", "error": "..."}
  - 重连成功发布 {"state": "ikuai_connected"}
  - 凭据只存在于本进程内存 + env，绝不落库、绝不下发前端（§69）
```

#### 5.1.3 PollScheduler（asyncio）

```python
class PollScheduler:
    """按不同频率调度采集任务；单终端连接查询互相错峰，避免瞬时打满 iKuai。"""

    tasks = [
        Task(name="terminals", interval=IKUAI_TERMINAL_POLL_INTERVAL),   # 10s
        Task(name="connections", interval=IKUAI_CONN_POLL_INTERVAL),     # 5s，内部把 N 个终端摊开成 N 个子任务，相位均匀分布
        Task(name="system", interval=IKUAI_SYSTEM_POLL_INTERVAL),        # 5s
        Task(name="wan", interval=WAN_DETECT_INTERVAL),                  # 300s
        Task(name="aggregate", interval=1.0),                            # 统计聚合 tick
        Task(name="broadcast", interval=BROADCAST_INTERVAL_MS/1000),     # WS 批量广播
        Task(name="persist", interval=60.0),                             # 写历史 rollup
    ]
```

关键点：

- **差分采样**：连接行中的 `total_up / total_down` 是累计值。ConnectionService
  以 `conn_key` 为单位保存上次采样值，速率 = `(cur - prev) / Δt`，Δt < 0 或
  计数回卷（路由器重启）时丢弃该轮差分。
- **连接生命周期**：
  - 新出现 conn_key → 产生 `packet` 事件（type=new）；
  - 存续 → 每 N 轮合并为一次 `update` 事件（携带最新累计值）；
  - 连续 2 轮未出现 → 标记 `closed`，产生最后一条事件后从活跃表移除。
- **错峰**：50 台终端 × 500 连接 ≈ 单轮 25k 行，摊到 5s 窗口内逐台查询。

#### 5.1.4 单进程开发模式

`config/dev.py` 且 `RUN_COLLECTOR_IN_PROCESS=1` 时，`AppConfig.ready()` 里用
daemon 线程跑同一个 collector 入口（复用全部代码路径）；生产环境该开关强制关闭。

### 5.2 Adapter / Normalizer（network/adapters）

输入：一行 iKuai conn 记录 + 上下文 `{terminal_ip, wan_ip, listen_ports}`；
输出：标准 Packet dict（对外唯一事件结构，前端 `adaptPacket()` 的直接输入）：

```jsonc
{
  "id": "pkt_000123",              // {conn_key 的 hash 前 12 位}#{seq}
  "seq": 10293,                    // 全局单调递增（Redis INCR）
  "timestamp": 1712450000.32,      // 秒（float）
  "born": 1712449987.10,           // 该连接首次发现时间
  "direction": "outbound",         // 后端判定，见 §6
  "app_name": "DNS",
  "protocol": "udp",
  "status": "已连接",               // "--" 归一为 null
  "source": {
    "ip": "192.168.2.100",
    "port": 60811,
    "domain": null,
    "lat": null, "lng": null       // 私网：由 lan_layout 伪坐标填充
  },
  "destination": {
    "ip": "114.114.114.114",
    "port": 53,
    "domain": null,
    "lat": 38.05, "lng": 114.51    // 公网：GeoService 填充；查不到为 null
  },
  "nat_info": {
    "forward_addr": "192.168.2.100",
    "src_port": 60811,
    "dst_port": 53,
    "original_dst": null           // inbound DNAT 时 = 公网IP:原端口
  },
  "total_up": 81,
  "total_down": 0,
  "interface": "wan1",
  "flag": null,                    // failed | lost | high_latency | null
  "latency_ms": null,              // 当前无真实来源，恒 null（诚实降级）
  "status_since": 1712450010.02
}
```

容错规则（对应 §61，adapter 内全部 try/except + 字段级清洗）：

| 原始值 | 清洗结果 |
|--------|----------|
| `"--"` / `""` / `"null"` / `None` | `null` |
| 数字字符串端口 `"443"` | `443` |
| 非法 IP（正则校验失败） | 整条记录丢弃，计数 `dropped_invalid_ip` |
| lat/lng 缺失或 (0,0) | `null`（地图端跳过绘制，统计不受影响） |
| protocol 大写/空 | lower()，空则 `"unknown"` |
| app_name 空 | `"未知应用"` |

flag 判定（当前可真实推导的只有 failed）：

```python
if status == "关闭连接" and (last_seen - born) < 5:
    flag = "failed"
else:
    flag = None        # lost / high_latency 无真实数据来源，保持 null，不伪造
```

### 5.3 ConnectionService（连接登记与速率）

```text
活跃连接表（Redis Hash net:conn:{key}）：
  conn_key = sha1(f"{local_ip}:{src_port}-{remote_ip}:{dst_port}-{protocol}")[:24]
  fields: first_seen, last_seen, total_up, total_down, up_bps, down_bps,
          direction, application, protocol, status, interface, nat_json, geo_json

流程：
  on_row(conn_row):
    key = conn_key(row)
    if key not in active:        create + emit packet(new)
    else:                        update totals/rates/status
    touch(key)                   # zset net:conn:index score=last_seen

  sweep():                        # 每轮结束调用
    for key in index where last_seen < now - 2*sweep_interval:
        emit packet(closed) → hdel
```

### 5.4 EventBus 与批量广播（core/event_bus.py）

```text
collector 各环节 → channel_layer.group_send("network", envelope)

信封（AGENTS.md §66）：
{
  "type": "packets",        // packets | traffic | stats | status | alert | heartbeat
  "timestamp": 1712450000.32,
  "data": {...}
}

广播节流：
  packet 事件先进入内存队列，broadcast 任务每 400ms 取整批发送
  （单批 ≤ 200 条，超出截断并顺延），保证前端 80ms flush 后渲染压力可控。
```

---

## 6. 方向判定规则（权威实现）

> 这是系统的正确性核心之一（§19、§22、§23、§42 禁止项）。实现位于
> `network/adapters/direction.py`，**纯函数**，输入输出确定，全量单测覆盖。

### 6.1 术语

```text
terminal_ip : 本次连接详询所查的内网设备 IP（iKuai monitor_lanip 查询目标）
forward_addr: conn 行内 NAT 后本地出口地址（可能等于 terminal_ip，
              也可能是上游 NAT 地址，如样例中 192.168.2.100）
local_ip    := forward_addr 若为私有 IP，否则 terminal_ip
remote_ip   := dst_addr（对端地址，iKuai 语义固定为“远端”）
src_port    := 本地端口；dst_port := 远端端口（对 remote 而言）
```

### 6.2 判定表

| # | local_ip | remote_ip | 判定 | 映射为标准 Packet |
|---|----------|-----------|------|-------------------|
| D1 | 私有 | 私有 | `internal` | source=local, destination=remote（只进 LAN 场景） |
| D2 | 私有 | 公网 | `outbound` | source=local, destination=remote |
| D3 | 私有 | 公网，且 `src_port ∈ LISTEN_PORTS` | `inbound`（端口映射/DNAT 回流） | source=remote(remote:dst_port)，destination=local(local:src_port)，nat.original_dst=`{wan_ip}:{src_port}` |
| D4 | 公网 | 公网 | `external`（异常/透传） | 不产生地图事件；仅计入 dropped 计数与 warn 日志 |
| D5 | 无法解析 / IP 非法 | — | 丢弃 | 计数 `dropped_unresolvable` |

补充约束：

- `LISTEN_PORTS` 来自环境变量（默认 `22,80,443,445,8080,8443,5001`），
  表示服务器对外暴露的服务端口。远期接入 iKuai NAT 规则表后自动推导，
  本期人工配置即可。
- **私网判断统一使用 `core.utils.network.is_private_ip()`**
  （10/8、172.16/12、192.168/16，另加 127/8、169.254/16、::1/128 保护性处理）。
- 判定结果一旦产出即随事件下发，前端、统计、聚合全部信任该值（P2）。

### 6.3 与真实样本的对照验证

`sdk/demo_result.json` 中的典型行：

| 样例行 | 判定过程 | 结果 |
|--------|----------|------|
| terminal=10.0.1.2, forward_addr=192.168.2.100, dst=114.114.114.114:53 udp | local=192.168.2.100(私有)， remote=公网， src_port=60811∉LISTEN_PORTS | `outbound` |
| terminal=X, forward_addr=X(私有), dst=162.159.61.8:443 tcp, src_port=40786 | src_port∉LISTEN_PORTS | `outbound` |
| terminal=10.0.1.2(SMB 服务), forward_addr=10.0.1.2, dst=203.119.238.180:57584 tcp, src_port=445∈LISTEN_PORTS | D3 | `inbound`，nat.original_dst={wan}:445 |
| terminal=A(私有), dst=192.168.2.1:53 | D1 | `internal`（仅 LAN 场景） |

以上样例将固化到 `tests/test_adapters_direction.py` 作为黄金用例。

---

## 7. Geo 地理服务

> 原则（§24）：坐标一律由后端给出，前端零 GeoIP 查询；私有 IP 永不定位（P3）。

### 7.1 Provider 抽象

```python
class GeoProvider(Protocol):
    def lookup(self, ip: str) -> GeoInfo | None:
        """GeoInfo(country, region, city, lat, lng, isp=None, source=str)"""
```

优先级链（高 → 低）：

1. `manual_overrides`：手工标注表（json/env），用于修正运营商库偏差；
2. `maxmind_provider`：GeoLite2-City（自带 lat/lng，全球覆盖）——默认启用；
3. `ip2region_provider`（可选）：中国城市粒度更准，输出省市名后再经
   内置「中国城市 → 经纬度」字典换算坐标；
4. 全部 miss → 返回 None（事件照常下发，lat/lng=null，地图不画线但统计保留）。

### 7.2 缓存

```text
L1 进程内 LRU（容量 4096，TTL 300s）
L2 Redis hash net:geo:{ip}，TTL 7d（GEO_CACHE_TTL）
L3 DB 表 network_geolookup（持久层，Redis 冷启动回源；见 §9.3）
```

### 7.3 服务器自身定位（网关节点）

```text
SERVER_LAT / SERVER_LNG 显式配置优先；
未配置时：collector 定期读取 iKuai WAN 口公网 IP → GeoProvider → 写 net:gateway。
LAN 设备坐标：lan_layout.ring_position(gateway, index) 在网关附近 ±0.05°
生成确定性伪坐标（同一设备每次布局一致），仅供 LAN 场景投影使用，
绝不参与公网地理语义。
```

---

## 8. Redis 实时数据层

所有 key 由 `core/redis_store.py` 独占读写，其他模块不得直接拼 key。

### 8.1 Key 设计

| Key | 类型 | 写入方 | 内容 | 保留策略 |
|-----|------|--------|------|----------|
| `net:seq` | string(INCR) | PacketService | 全局事件序号 | 永久 |
| `net:packets` | zset(score=seq) | PacketService | 最近事件完整 JSON（成员=packet id） | 条数上限 `PACKET_BUFFER_MAX`=10000，ZREMRANGEBYRANK 淘汰 |
| `net:packet:{id}` | string(TXT json) | PacketService | 事件体（zset 成员只存 id） | 与 zset 同步删除 |
| `net:conn:{key}` | hash | ConnectionService | 活跃连接全量字段 | 关闭后删除 |
| `net:conn:index` | zset(score=last_seen) | ConnectionService | 过期扫描索引 | sweep 清理 |
| `net:bw:{window}s` | list[[t,up,down]] | Aggregator | 带宽时间序列，秒级点 | 长度=窗口长度（最大 3600 点） |
| `net:cnt:{dim}:{bucket_ts}` | hash | Aggregator | 维度计数：`{dim}=directions\|protocols\|apps\|ports\|countries\|ips`，field=value | bucket 粒度 60s，TTL=最长窗口+120s |
| `net:totals` | hash | Aggregator | total/active/closed/failed/lost 累计 | 永久（重启清零可接受） |
| `net:devices` | hash(ip→json) | DeviceService | 内网设备表（含 ring_index、伪坐标、速率） | 消失 3 轮后移除 |
| `net:nodes` | hash(ip→json) | StatusService | 公网热点节点表（按流量 TopN=64 动态生成） | 每轮重建 |
| `net:gateway` | hash | StatusService | {lat,lng,wan_ip,updated_at} | 永久覆盖 |
| `net:mode` | hash | StatusService | mode/uptime/started_at | 永久覆盖 |
| `net:ikuai:health` | hash | SessionManager | state/error/last_poll_at/connected_at | 覆盖式 |
| `net:sys:metrics` | hash | collector(system) | cpu_percent/memory_percent/uptime | 覆盖式 |
| `net:geo:{ip}` | hash | GeoService | 国家/城市/经纬度 | TTL 7d |
| `asgi:group:network` | channels 组 | Channel Layer | WS fan-out | 框架管理 |

### 8.2 滚动窗口统计（Aggregator）

```text
支持窗口（AGENTS.md §57）：5 / 30 / 60 / 300 / 900 / 3600 秒

实现：
  - 每个 60s bucket 一个 hash（net:cnt:{dim}:{bucket_ts}），HINCRBY 累加
  - 查询 window 时取 ceil(window/60) 个 bucket 合并求和排序 TopN
  - 5s/30s 窗口由 1s tick 的内存滑动窗补齐（进程内 deque），保证小窗口灵敏度
  - bandwidth 序列同理：1s 内存 deque（近 60s） + Redis list（长窗口）

带宽计算（无接口级速率数据时的兜底公式）：
  up_bps(t)   = Σ(conn.up_bps)   ，其中 conn.up_bps = Δtotal_up / Δt
  平滑：EWMA α=0.4，抑制 iKuai 采样抖动；Δt≤0 的样本丢弃
```

---

## 9. 数据库设计

### 9.1 建模原则

- 实时数据全部在 Redis；DB 只承担三类冷数据：**历史曲线、审计留痕、Geo 二级缓存**（§64，防止过度建模）。
- 默认 SQLite 即可运行全功能；`DB_ENGINE=postgres` 切换生产。
- 所有时间字段存 UTC；API 输出 unix 秒。

### 9.2 ER 总览

```text
analytics_trafficsnapshot        network_flowrecord (可选)        core_systemevent
─────────────────────────        ─────────────────────────        ────────────────
id            PK                 id            PK                 id            PK
ts            idx                flow_key      idx                ts            idx
bucket_s                         first_seen                       level
up_bytes/down_bytes              last_seen  idx                   code
up_bps/down_bps                  direction                        message
pkts_total                       protocol/application             context(JSON)
pkts_out/in/internal             src_ip/src_port/dst_ip/dst_port
conn_active                      domain/nat_forward_addr
created_at                       bytes_up/bytes_down, pkts
                                 src_country/src_lat/lng …
                                 status/interface

network_geolookup
─────────────────
ip_prefix  unique
country/region/city, lat, lng, source, updated_at
```

### 9.3 表明细

#### 9.3.1 `analytics_trafficsnapshot` —— 分钟级历史 rollup

| 字段 | 类型 | 说明 |
|------|------|------|
| id | BIGPK | |
| ts | DateTimeField(6), **index** | 分钟桶起点（UTC） |
| bucket_s | IntegerField, default=60 | 桶粒度（预留 5m/1h 聚合） |
| up_bytes / down_bytes | BigIntegerField | 该分钟上传/下载字节 |
| up_bps / down_bps | FloatField | 平均速率 |
| pkts_total / pkts_outbound / pkts_inbound / pkts_internal | IntegerField | 事件数 |
| conn_active_max | IntegerField | 活跃连接峰值 |
| created_at | auto | |

用途：支撑「超过 Redis 保留期」的历史趋势（后续时间范围扩展）、离线分析。
唯一约束：`(ts, bucket_s)`。

#### 9.3.2 `network_flowrecord` —— 连接审计（默认关闭）

`FLOW_PERSIST=false` 时完全不写库。开启后由 ConnectionService 在连接
**关闭时** 异步落一条（批量 bulk_create，每 30s 一批）。

| 字段 | 类型 | 说明 |
|------|------|------|
| flow_key | CharField(24), **index** | conn_key |
| first_seen / last_seen | DateTimeField(6), **index(last_seen)** | |
| direction | CharField(8) | outbound/inbound/internal |
| protocol / application | CharField(16)/CharField(64) | |
| src_ip / src_port / dst_ip / dst_port | 字段组 | 归一后的端点 |
| domain | CharField(255), null | |
| nat_forward_addr | CharField(64), null | |
| bytes_up / bytes_down | BigIntegerField | 累计 |
| pkts | IntegerField | 采样次数 |
| src_country / src_city / src_lat / src_lng | Geo 冗余 | 及 dst_* 对称字段 |
| status / interface | CharField | 关闭前最后状态 |

索引：`(last_seen)`（清理）、`(direction, last_seen)`、`(src_ip)`。
保留：`prune_history` 默认删 7 天前记录。

#### 9.3.3 `network_geolookup` —— Geo 二级持久缓存

| 字段 | 类型 | 说明 |
|------|------|------|
| ip_prefix | CharField(64), **unique** | 精确 IP 或 /24 前缀 |
| country / region / city | CharField | |
| lat / lng | FloatField, null | |
| source | CharField(16) | maxmind / ip2region / manual |
| updated_at | auto | |

Redis 未命中且进程内也未命中时读此表；Provider 查到后异步回填。

#### 9.3.4 `core_systemevent` —— 系统事件/告警留痕

| 字段 | 类型 | 说明 |
|------|------|------|
| ts | DateTimeField(6), **index** | |
| level | CharField(8) | info / warn / error |
| code | CharField(32) | `IKUAI_DISCONNECTED` / `GEO_PROVIDER_FAIL` / `COLLECTOR_ERROR` … |
| message | TextField | |
| context | JSONField, default=dict | 结构化上下文 |

用途：WS `alert` 事件的持久底账；前端事件流未来可拉取历史告警。

### 9.4 迁移策略

- 开发期 SQLite 直接 `migrate`；切 PostgreSQL 时新建库后 `migrate` +
  `prune_history` 无需数据搬迁（历史数据可弃）。
- Migration 必须入库评审（工程要求 §73）；禁止 `--fake` 上生产。

---

## 10. REST API 设计

### 10.1 通用约定

| 项 | 约定 |
|----|------|
| Base URL | `{NEXT_PUBLIC_API_URL}`，如 `http://localhost:8000` |
| 编码 | UTF-8 JSON，DRF 渲染器仅保留 JSONRenderer |
| 时间 | Unix 秒（float）；前端 `types.ts` 已按秒消费 |
| 幂等 | 全部只读 GET；无鉴权（内网部署，见 §13） |
| 错误格式 | `{"error": {"code": "<snake_case>", "message": "<人类可读>"}}` + 正确 HTTP 状态码 |
| 限流 | DRF AnonRateThrottle：`/api/packets` 10/s，其余 5/s（防误刷，正常轮询远低于此） |
| Schema | `/api/schema/`（drf-spectacular OpenAPI 3）+ `/api/schema/swagger-ui` |
| CORS | 白名单来自 `DJANGO_CORS_ORIGINS`（§13） |

### 10.2 v1 核心 API（★ 与前端现有契约逐字节兼容）

前端 `frontend/src/lib/api/client.ts` 已按以下契约实现并在线运行，
**字段名、嵌套结构、蛇形命名均不可变更**；新增字段只能向后追加。

#### 10.2.1 `GET /api/mode` — 运行模式与网关状态

```jsonc
// 200
{
  "mode": "ikuai",                 // ikuai | mock
  "uptime": 86241,                 // collector 启动至今秒数
  "gateway": {
    "lat": 31.2304,                // 服务器/网关公网定位；未知为 null
    "lng": 121.4737
  },
  "ikuai": {
    "router_url": "http://10.1.1.1",
    "error": null,                 // 最近错误文本；正常为 null
    "last_poll_at": 1712450000.1,  // 最近成功轮询时间（秒）；从未成功为 null
    "connected_at": 1712441300.0   // 本次会话建立时间
  }
}
```

#### 10.2.2 `GET /api/packets?since={seq}&limit=500` — 增量事件拉取

```jsonc
// 200
{
  "server_time": 1712450000.98,
  "last_seq": 10293,               // 当前全局序号（客户端下次 since 用它）
  "events": [ /* §5.2 标准 Packet 数组，按 seq 升序 */ ]
}
```

| 参数 | 说明 |
|------|------|
| `since` | 客户端已消费的最大 seq；返回 `(since, now]` 区间事件；缺省=最近一页 |
| `limit` | 默认 500，上限 1000（超出按最旧截断，客户端以下一轮补齐） |

语义：这是 WebSocket 的 HTTP 兜底通道。断线重连后前端用它做 gap backfill；
`events=[]` 且 last_seq 不变表示无新数据（不是错误）。

#### 10.2.3 `GET /api/stats?window=300` — 全局统计快照

| 参数 | 取值 |
|------|------|
| `window` | 5 / 30 / 60 / 300 / 900 / 3600（秒），非法值回落 300 |

```jsonc
// 200
{
  "total": 18294,                  // 会话期内事件总数
  "active": 530,                   // 活跃连接数
  "closed": 17764,
  "failed": 213,                   // flag=failed 计数
  "lost": 0,                       // 预留（当前恒 0，不伪造）
  "directions": { "outbound": 72391, "inbound": 38291, "internal": 17810 },
  "protocols": { "tcp": 12000, "udp": 5000, "quic": 1294 },   // 动态，不写死
  "apps": [ { "name": "Cloudflare", "count": 821 } ],          // TopN=20
  "bandwidth": {
    "up_bps": 8420000000.0,        // B/s
    "down_bps": 5310000000.0,
    "series": [[1712449400, 100.5, 80.2], ...]   // [t, upBps, downBps]，点数≈min(window,60)
  },
  "loss_rate": 0.0,                // 预留（恒 0）
  "avg_latency_ms": 0.0,           // 预留（恒 0，直到有真实探测源）
  "system": { "cpu_percent": 12.5, "memory_percent": 63.0 },   // iKuai 不可得时为 null
  "latency_heatmap": { "x": [...], "y": [...], "data": [...] },// 可选，暂恒为空结构
  "mode": "ikuai",
  "uptime": 86241,
  "window": 300
}
```

> 扩展维度（countries / ports / ips）不在本接口堆字段，走 §10.3 专用接口，
> 保持 v1 快照体积稳定（该接口 2s 轮询一次）。

#### 10.2.4 `GET /api/devices` — 内网设备（LAN 场景）

```jsonc
// 200
{
  "devices": [
    {
      "ip": "10.0.1.2",
      "mac": "60:be:b4:05:f3:67",     // iKuai 提供，缺失省略字段
      "hostname": "iStoreOS",         // 取自 comment，缺失省略
      "vendor": null,
      "interface": "lan1",
      "is_gateway": true,             // == wan 网关或 SERVER_IP 匹配
      "ring_index": 0,                // LAN 布局序号（确定性）
      "lat": 31.2311, "lng": 121.4741,// 伪坐标（lan_layout）
      "connections": 530,
      "up_rate": 10240.0,             // B/s（差分）
      "down_rate": 20480.0
    }
  ]
}
```

#### 10.2.5 `GET /api/nodes` — 公网节点（地图光点）

```jsonc
// 200
{
  "nodes": [
    { "ip": "162.159.61.8", "name": "dns.cloudflare.com", "domain": "dns.cloudflare.com",
      "lat": 37.7749, "lng": -122.4194, "type": "server" }
    // type: gateway(本端出口)|server|client；按会话期流量 Top64 动态生成
  ]
}
```

#### 10.2.6 `GET /api/health`

```jsonc
{ "status": "ok", "redis": true, "db": true, "collector_age_s": 2.1 }
// collector_age_s > 3×轮询周期时 status="degraded"；任一依赖 false 时 503
```

### 10.3 v2 扩展 API（/api/network/*，对应 AGENTS.md §25）

v1 稳定后追加，全部支持 `window` 参数（同 10.2.3 取值）与 `limit`（默认 20，上限 100）。

| Method | Path | 说明 | 响应要点 |
|--------|------|------|----------|
| GET | `/api/network/overview/` | 大屏首屏一次性数据（stats+devices 摘要+nodes 计数） | 聚合多源，减少首屏请求数 |
| GET | `/api/network/flows/?window=&direction=&search=` | 归一化流列表（供连接详情/检索） | 分页 limit/offset；元素=§5.2 Packet |
| GET | `/api/network/flows/{flow_key}/` | 单连接详情（点击流面板） | 含 nat_info、geo、生命周期时间 |
| GET | `/api/network/connections/?window=` | 活跃连接表（conn_key 视角，非单包） | `{count, items:[{key,direction,application,bytes,rates,age_s}]}` |
| GET | `/api/network/countries/?window=` | TOP COUNTRIES | `[{country, code, packets, bytes, connections}]` |
| GET | `/api/network/protocols/?window=` | 协议占比（动态） | `[{protocol, packets, bytes}]` |
| GET | `/api/network/applications/?window=` | 应用占比（动态） | `[{name, packets, bytes}]` |
| GET | `/api/network/ports/?window=&role=dst` | TOP PORTS | `[{port, protocol, packets, connections}]` |
| GET | `/api/network/ips/?role=source&window=` | TOP SOURCE/DEST IP | `[{ip, country, packets, bytes, connections}]` |
| GET | `/api/network/events/?level=&limit=` | 系统/告警事件历史（SystemEvent） | `[{ts, level, code, message}]` |
| GET | `/api/network/history/?metric=bps&from=&to=&bucket=60` | 历史 rollup 曲线（TrafficSnapshot） | `[{t, up, down}]` |

响应统一信封：

```jsonc
// 成功：数据本体（数组型包一层 {"items": [...], "total": n}）
// 失败：{"error": {"code": "invalid_window", "message": "window must be one of 5,30,60,300,900,3600"}}
```

---

## 11. WebSocket 设计

### 11.1 基本信息

```text
URL        ws(s)://host/ws/network/          （可选 ?since=<seq> 断线补发）
Group      "network"
Origin     校验白名单（DJANGO_CORS_ORIGINS 同源策略），非法 Origin 拒绝 code=4003
并发模型    consumer 只做订阅转发，零业务逻辑、零 DB 访问
```

### 11.2 生命周期

```text
connect ──▶ accept（校验 Origin）
        ──▶ group_add("network")
        ──▶ 下发 hello + snapshot（让新客户端立即有数据，不等下一轮广播）
disconnect ──▶ group_discard
```

### 11.3 消息类型表（Server → Client）

信封统一（§66）：`{"type": str, "timestamp": float, "data": object}`

| type | 频率 | data 内容 | 说明 |
|------|------|-----------|------|
| `hello` | 连接建立 1 次 | `{server_time, seq, mode, uptime}` | 会话握手 |
| `snapshot` | hello 后 1 次 | 完整 `/api/stats` 结构 | 初始渲染基线 |
| `packets` | ~400ms 批量 | `{last_seq, events: Packet[]}` | ★ 核心事件流；单批 ≤200 |
| `traffic` | 1s | `{t, up_bps, down_bps}` | 带宽心跳（比 stats 轮询更细） |
| `stats` | 变更节流 ≥2s | 完整 stats 快照 | 与 `/api/stats` 同构 |
| `devices` | 变更节流 ≥2s | `{devices:[...]}` | 与 `/api/devices` 同构 |
| `nodes` | 变更节流 ≥2s | `{nodes:[...]}` | 与 `/api/nodes` 同构 |
| `status` | 状态迁移时 | `{state, ikuai:{...}, gateway:{...}}` | iKuai 断连/恢复/模式切换 |
| `alert` | 发生时 | `{level, code, message, context}` | 预留扩展位（本期仅系统级） |
| `heartbeat` | 15s | `{t}` | 保活；前端 45s 未收到视为断线 |

### 11.4 Client → Server

| type | 说明 |
|------|------|
| `ping` | 服务端回 `{type:"pong"}`（部分代理环境禁用 WS ping frame 时的兜底） |
| `subscribe` | 预留：`{"type":"subscribe","scenes":["global","china","lan"]}`，本期忽略 |

未知 type：静默忽略并 debug 日志（向前兼容）。

### 11.5 断线重连与数据补齐（与前端 §58 对应）

```text
前端持有 last_seq：
  1) WS 断开 → 显示 DATA STREAM DISCONNECTED / RECONNECTING...
  2) 指数退避重连（1s 起，×2，封顶 30s）
  3) 连接成功 → 若 now-last_recv > 5s，先调 GET /api/packets?since=last_seq
     补齐缺口（上限 1000 条，更多缺口放弃补齐、以 snapshot 重置基线）
  4) 恢复 DATA STREAM CONNECTED
```

### 11.6 Channels 配置

```python
# config/asgi.py
application = ProtocolTypeRouter({
    "http": django_asgi_app,
    "websocket": AllowedHostsOriginValidator(AuthMiddlewareStack(
        URLRouter(network.routing.websocket_urlpatterns))),
})
CHANNEL_LAYERS = {"default": {
    "BACKEND": "channels_redis.core.RedisChannelLayer",
    "CONFIG": {"hosts": [env("REDIS_URL")], "capacity": 2000, "expiry": 30},
}}
```

---

## 12. Mock 模式设计

> 目标：`DATA_SOURCE=mock` 时无需 iKuai 即可全链路演示，且 Mock 与 Real
> 共享 100% 相同的下游管线（P8，禁止第二套 UI 数据）。

```text
datasource/mock/generator.py
  - 输入：场景剧本 scenarios.py（outbound 高峰 / inbound 攻击面 / internal DNS /
    NAT 端口映射 / 混合常态 五种内置剧本）
  - 输出：与 iKuai conn 行【字段级一致】的原始行
    （protocol/status/dst_addr/src_port/dst_port/forward_addr/app_name/
     interface/total_up/total_down/domain）
  - 特意注入脏数据（"--"、null、非法端口、缺失坐标）以持续验证前端容错

调度：复用 PollScheduler，interval=1s；SessionManager 替换为 NoopSession。
开关：DATA_SOURCE=ikuai|mock（默认 ikuai）；/api/mode 的 mode 字段如实上报，
前端 Header 显示当前数据源，杜绝真假混跑（§79）。
```

---

## 13. 安全设计

### 13.1 凭据与秘密

- iKuai 账号密码、Django SECRET_KEY、数据库连接 **只存在于 `.env`**（不入库、
  不入 git、绝不下发任何 API/WS 消息）（§69）。
- `.env.example` 提供占位模板；`config/settings/prod.py` 强制要求 SECRET_KEY
  显式注入，缺失即启动失败。
- 浏览器可达的信息只有：脱敏后的 `router_url` 主机名（/api/mode 已如此）。

### 13.2 CORS / CSRF / Host

| 项 | dev | prod |
|----|-----|------|
| `ALLOWED_HOSTS` | `localhost,127.0.0.1` | env 显式列出域名 |
| `CORS_ALLOWED_ORIGINS` | `http://localhost:3000` | env 显式列出 |
| CSRF | API 全 GET 无 CSRF 面 | 同左；管理后台如启用另配 |
| WS Origin | `AllowedHostsOriginValidator` | 同左 + 反代传 Host |
| SECURE_* | 关闭 | HSTS、SSL redirect、secure cookies（视部署有无 TLS） |
| DEBUG | True | False（强制） |

### 13.3 其他

- REST 全只读 + 匿名限流（§10.1）；未来如暴露公网，加 `X-API-Key` 中间件
  （预留 `settings.API_KEY`，空=不启用）。
- iKuai 管理界面永不经本后端代理（§69）；collector 是唯一出站调用方。
- 日志脱敏：任何日志不得打印 cookie_header / password / sess_key。

---

## 14. 性能与容量规划

### 14.1 目标规模（家庭/小型机房场景）

| 指标 | 预估 |
|------|------|
| 内网终端 | ≤ 64 |
| 每轮连接行 | ≤ 64 × 500 = 32k |
| 归一化事件速率 | 常态 < 50 events/s，峰值 < 500 events/s |
| WS 客户端 | ≤ 20 并发 |

### 14.2 关键预算

| 项 | 预算 | 手段 |
|----|------|------|
| 事件入库延迟 | < 100ms | 批量 pipeline 写 Redis |
| WS 端到端延迟 | < 600ms | 400ms 批播 + 直发 |
| /api/stats P95 | < 30ms | 纯 Redis 读 + 进程内存滑窗 |
| /api/packets P95 | < 30ms | zset range + mget |
| Redis 内存 | < 80 MB | 环形缓冲上限 + bucket TTL（§8.1） |
| collector CPU | < 15% 单核 | 差分增量、错峰轮询、Geo LRU |
| DB 写入 | 1 行/分钟 + 可选批量 flowrecord | persist tick |

### 14.3 反压与降级

```text
- 广播队列 > 5000 条：丢最旧 packet 批，保 traffic/stats/status（保命优先）
- Redis 不可达：collector 停止产生事件并发布 status(alert)，web 返回 503 health；
  恢复后自动续跑（所有写入幂等）
- iKuai 不可达：进入 SessionManager 退避循环，前端呈现 DISCONNECTED 态（§58）
- 单事件处理永不抛出到主循环：顶层 try/except + error 计数器
```

---

## 15. 错误处理与日志

### 15.1 降级矩阵

| 故障 | 检测 | 用户可见表现 | 自动恢复 |
|------|------|--------------|----------|
| iKuai 登录失败 | Result≠10000 | Header DATA STREAM ⚠ + /api/mode.ikuai.error | 退避重登 |
| iKuai 调用超时 | SDK NetworkError | 同上，last_poll_at 停更 | 退避重试 |
| Redis 宕机 | ping fail | /api/health 503，WS 静默 | 重连后续跑 |
| Geo Provider 异常 | 单次 lookup try/except | 事件 lat/lng=null（地图少线，统计正常） | 下一 IP 重试 |
| 脏数据行 | adapter 清洗 | 无感（丢弃计数递增） | — |
| DB 不可写 | persist tick 异常 | 历史曲线停更，实时不受影响 | 下个周期重试 |

### 15.2 日志规范

```text
logger 命名：datasource.ikuai / network.adapter / network.service / analytics / ws
级别：LOG_LEVEL env 控制，prod 默认 INFO
格式：<ts> <level> <logger> <code> <kv...>（structlog kv 风格）
必打点：
  - collector 每轮摘要（DEBUG）：rows_in, new, updated, closed, dropped
  - session 重登（WARN）、连续失败（ERROR）
  - 广播丢弃（WARN，含队列水位）
  - API 5xx（ERROR，含 path + error.code）
指标兜底：net:totals 内维护 dropped_invalid_ip / dropped_unresolvable 等计数，
可经 /api/health 附带输出，便于验收核对「零伪造数据」。
```

---

## 16. 配置项清单

`.env.example`（全部变量及默认值）：

```bash
# ---- Django ----
DJANGO_SECRET_KEY=change-me
DJANGO_DEBUG=1
DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1
DJANGO_CORS_ORIGINS=http://localhost:3000

# ---- 存储 ----
DATABASE_URL=sqlite:///netscope.db          # 或 postgres://user:pass@host:5432/netscope
REDIS_URL=redis://127.0.0.1:6379/0

# ---- 数据源 ----
DATA_SOURCE=ikuai                           # ikuai | mock
RUN_COLLECTOR_IN_PROCESS=1                  # 仅 dev；prod 必须 0

# ---- iKuai ----
IKUAI_ROUTER_URL=http://10.1.1.1
IKUAI_USERNAME=admin
IKUAI_PASSWORD=
IKUAI_TERMINAL_POLL_INTERVAL=10
IKUAI_CONN_POLL_INTERVAL=5
IKUAI_SYSTEM_POLL_INTERVAL=5
IKUAI_REQUEST_TIMEOUT=8

# ---- 网络/拓扑 ----
LISTEN_PORTS=22,80,443,445,8080,8443,5001   # inbound 判定依据（§6）
SERVER_LAT=                                  # 留空则自动 GeoIP WAN 出口
SERVER_LNG=

# ---- Geo ----
GEO_PROVIDER=maxmind                        # maxmind | off（off=不下发坐标）
GEO_MAXMIND_CITY_DB=path/to/GeoLite2-City.mmdb
GEO_IP2REGION_XDB=                          # 可选中国增强
GEO_CACHE_TTL=604800

# ---- 实时层 ----
PACKET_BUFFER_MAX=10000
STATS_WINDOWS=5,30,60,300,900,3600
BROADCAST_INTERVAL_MS=400
FLOW_PERSIST=0                              # 1=连接关闭落库（审计）
SNAPSHOT_RETENTION_DAYS=30
FLOW_RECORD_RETENTION_DAYS=7

# ---- 日志 ----
LOG_LEVEL=INFO
```

---

## 17. 测试策略

| 层 | 手段 | 关键用例 |
|----|------|----------|
| direction 纯函数 | pytest 参数化 | §6.3 四条黄金样例 + 边界（回环地址、IPv6、LISTEN_PORTS 命中/未命中） |
| packet adapter | 黄金样本 + 模糊测试 | 以 demo_result.json 裁剪 fixture；随机注入 None/"--"/负数/超长串，断言永不抛异常 |
| connection lifecycle | 假时钟单测 | 新建/更新/差分回卷/两轮消失判闭 |
| aggregator | 假时钟 | 窗口合并正确性、bucket 过期、EWMA 平滑 |
| REST | DRF APITestCase | 契约快照测试：响应 JSON 与本文档示例 diff（防字段漂移） |
| WS | Channels ApplicationCommunicator | hello/snapshot 顺序、批量上限、Origin 拒绝、ping/pong |
| Geo | mock provider | 缓存命中链路 L1→L2→DB→provider、私网短路 |
| Mock 模式 | 端到端 | DATA_SOURCE=mock 起全栈，断言事件结构与 ikuai 模式一致 |

覆盖率门槛：`adapters/ services/ analytics/` ≥ 85%。

---

## 18. 部署方案

### 18.1 开发环境（docker-compose.dev.yml）

```yaml
services:
  redis:
    image: redis:7-alpine
  backend:
    build: ./backend
    command: sh -c "python manage.py migrate &&
                    python manage.py collect_network & 
                    daphne -b 0.0.0.0 -p 8000 config.asgi:application"
    env_file: backend/.env
    ports: ["8000:8000"]
  frontend:
    build: ./frontend
    environment:
      NEXT_PUBLIC_API_URL: http://localhost:8000
      NEXT_PUBLIC_WS_URL: ws://localhost:8000/ws/network/
    ports: ["3000:3000"]
```

### 18.2 生产（对应 §71、§72）

```text
Internet ─▶ Nginx(443)
             ├─ /            → Next.js (node:3000 或静态导出+CDN)
             ├─ /api/        → daphne :8000
             └─ /ws/network/ → daphne :8000  （Upgrade/Connection 头必配）
Django(daphne ×2, systemd/compose) ─▶ Redis ─▶ iKuai
                                   └▶ PostgreSQL
collector 独立 systemd 单元（Restart=always）
```

Nginx WS 片段要点：

```nginx
location /ws/network/ {
    proxy_pass http://127.0.0.1:8000;
    proxy_http_version 1.1;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection "upgrade";
    proxy_read_timeout 75s;          # 心跳 15s，足够
}
```

### 18.3 例行维护

```bash
python manage.py prune_history        # cron: 每日 04:00
python manage.py migrate              # 发版流程
curl localhost:8000/api/health        # 监控探针
```

---

## 19. 开发里程碑

对齐 AGENTS.md §82 的 Phase 划分（后端视角）：

| Phase | 交付物 | 验收 |
|-------|--------|------|
| P1 | 项目骨架、settings(dev/prod)、docker-compose、/api/health、Redis 连通 | compose up 三容器互通 |
| P2 | datasource(iKuai/Mock) + adapters + PacketService；/api/mode /api/packets /api/stats 打通；WS consumer 广播 mock 包 | 前端现有轮询立即出数 |
| P3 | ConnectionService 差分速率、Aggregator 全维度、/api/devices /api/nodes | 前端面板/雷达/排名全部点亮 |
| P4 | GeoService（MaxMind+缓存+私网短路）、lan_layout、gateway 定位 | GLOBAL/CHINA/LAN 三场景坐标正确 |
| P5 | direction 权威规则 + LISTEN_PORTS inbound 识别 + NAT original_dst | NAT Pipeline 面板数据完整 |
| P6 | /api/network/* v2 扩展接口 + drf-spectacular schema | swagger 全绿 |
| P7 | SystemEvent/alert 通道、FLOW_PERSIST、prune_history | 告警可见、历史可查 |
| P8 | 性能调优（批播/背压/缓存）、降级矩阵演练、压测报告 | §14 预算达标 |
| P9 | 接真实 iKuai 验收：DATA_SOURCE=ikuai，Mock 自动关闭 | §83 后端清单全勾 |

---

## 20. 附录

### 20.1 iKuai 原始字段 → 标准字段对照

来源：`sdk/demo_result.json` 实测（terminal_connections[].conn[]）。

| iKuai 字段 | 实测样例 | 归一去向 |
|------------|----------|----------|
| `dst_addr` | `114.114.114.114` | outbound: destination.ip ／ inbound(D3): source.ip |
| `dst_port` | `53` | 对端端口（注意：iKuai 语义是“远端端口”，非“目的服务端口”） |
| `src_port` | `60811` | 本地端口（inbound 时即服务监听端口） |
| `forward_addr` | `192.168.2.100` | nat_info.forward_addr；私有则覆盖 local_ip |
| `app_name` | `DNS`/`Cloudflare`/`未知协议` | application（原样保留中文分类） |
| `protocol` | `udp`/`tcp` | protocol(lower) |
| `status` | `已连接`/`请求连接`/`等待`/`关闭连接`/`--` | status（`--`→null） |
| `interface` | `wan1` | interface |
| `total_up` / `total_down` | `81` / `0` | bytes.upload/download（累计值；速率由后端差分） |
| `domain` | `--`/域名 | 对端 domain（`--`→null） |

终端列表行（monitor_lanip TYPE=data）关键字段：

| iKuai 字段 | 归一去向 |
|------------|----------|
| `ip` | devices[].ip / terminal_ip 上下文 |
| `mac` | devices[].mac |
| `comment` | devices[].hostname |
| `client_type` / `interface` | devices[].interface 参考 |
| `connect_num` | devices[].connections |
| `upload` / `download` | 设备级速率基准（可与连接差分交叉校验） |

### 20.2 状态字典（iKuai 实测枚举）

```text
"--"（无状态，如 UDP）→ null
"请求连接" SYN_SENT 类    "已连接" ESTABLISHED 类
"等待" TIME_WAIT 类        "关闭连接" CLOSED 类 → flag=failed（寿命<5s 时）
```

### 20.3 术语表

| 术语 | 定义 |
|------|------|
| Packet（事件） | 后端产出的最小通知单元（连接的新增/更新/关闭），非网络层 packet |
| conn_key | 连接稳定标识：sha1(local:port-remote:port-proto)[:24] |
| Flow / NetworkFlow | 前端 types.ts 的标准化视图，源自本文件 §5.2 Packet |
| LISTEN_PORTS | 服务器主动暴露的服务端口集合，inbound 判定依据 |
| 伪坐标 | LAN 设备围绕网关生成的确定性展示坐标，无地理含义 |

### 20.4 验收对照（AGENTS.md §83 后端项）

- [x] Django / DRF / Channels / Redis / WebSocket —— §3
- [x] API 契约兼容前端 + v2 扩展 —— §10
- [x] Adapter（含脏数据容错）—— §5.2、§17
- [x] Aggregation（滚动窗口/TopN/带宽差分）—— §8.2
- [x] 方向权威在后端、私网不定位 —— §6、§7
- [x] Mock/Real 同管线可切换 —— §12
- [x] 环境变量 / 安全 / Nginx / Migration / README —— §13、§16、§18
