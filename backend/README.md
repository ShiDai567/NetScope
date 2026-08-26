# NetScope Backend

GLOBAL NETWORK INTELLIGENCE CENTER —— Django 后端。
设计文档见 [doc/backend-design.md](../doc/backend-design.md)。

## 架构

```text
iKuai Router ──HTTP──▶ Collector (collect_network)
                          │  SessionManager + IKuaiGateway (sdk/)
                          │  Adapter: 方向判定 D1-D5 / 字段清洗 / NAT 解析
                          │  GeoService: MaxMind + 手工覆盖 + Redis 缓存
                          ▼
                    Redis 实时层 (net:*) ──▶ Aggregator (滚动窗口/带宽 EWMA)
                          │                        │
                          ▼                        ▼
              DRF REST /api/*          Channels /ws/network/ (批量广播 400ms)
                          └────────┬───────────────┘
                                   ▼
                        PostgreSQL (快照/审计/事件，冷数据)
```

## 快速开始

```bash
cd backend
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt -r requirements-dev.txt
cp .env.example .env          # 填入 Redis/PostgreSQL/iKuai 凭据
.venv/bin/python manage.py migrate
```

启动（开发，进程内采集）：

```bash
.venv/bin/python manage.py runserver 0.0.0.0:8000
# RUN_COLLECTOR_IN_PROCESS=1 时采集线程随服务启动
```

启动（生产，双进程）：

```bash
.venv/bin/python manage.py collect_network        # 采集器
.venv/bin/daphne -b 0.0.0.0 -p 8000 config.asgi:application
```

## API

| 接口 | 说明 |
|------|------|
| `GET /api/mode` | 数据源模式、网关定位、iKuai 健康状态 |
| `GET /api/packets?since={seq}` | 增量事件拉取（断线补齐通道） |
| `GET /api/stats?window={5..3600}` | 全局统计快照（6 档窗口） |
| `GET /api/devices` | 内网设备表（LAN 环形布局坐标） |
| `GET /api/nodes` | 公网热点节点（流量 Top64 + Geo 坐标） |
| `GET /api/health` | 健康检查（redis + collector 心跳） |
| `GET /api/network/{countries,protocols,applications,ports,ips}` | 维度排名 |
| `GET /api/network/{connections,events,history}` | 连接表 / 系统事件 / 历史 rollup |
| `WS /ws/network/` | 实时通道：hello/snapshot/packets/traffic/stats/status/alert/heartbeat |
| `GET /api/schema/` + `/api/schema/swagger-ui/` | OpenAPI 3 文档 |

## 测试

```bash
.venv/bin/python -m pytest tests/ -q
```

覆盖：方向判定黄金用例（D1-D5）、脏数据模糊测试、连接生命周期与速率差分、
聚合窗口、Geo 缓存链路、API 契约（与前端 client.ts 逐字段对齐）、WS 消费者。

## 关键配置

见 `.env.example`，完整说明见设计文档 §16。

| 变量 | 说明 |
|------|------|
| `DATA_SOURCE` | `ikuai`（真实路由器）/ `mock`（同管线模拟） |
| `LISTEN_PORTS` | 入站判定依据：本地端口命中即 inbound（D3 规则） |
| `IKUAI_SSL_VERIFY` | 自签面板证书校验开关（默认 0） |
| `GEO_MAXMIND_CITY_DB` | GeoLite2-City.mmdb 路径（`data/` 下已有） |
| `RUN_COLLECTOR_IN_PROCESS` | 1=采集线程随 Django 启动（开发） |

## 例行维护

```bash
.venv/bin/python manage.py prune_history    # cron 每日：清理过期快照/审计/事件
```

## 目录

```text
config/      settings(dev/prod) + asgi/urls/routing
core/        redis_store / event_bus / geo / lan_layout / utils
datasource/  ikuai(session/gateway/scheduler/funcs) + mock
network/     adapters(direction/packet) + services + consumers + views + collector
analytics/   aggregators(滚动窗口) + bandwidth(EWMA) + models(TrafficSnapshot)
tests/       方向黄金用例 / 契约 / 容错 / WS 集成
```
