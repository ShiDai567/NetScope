# GLOBAL NETWORK INTELLIGENCE CENTER

## 一、项目定位

请你作为一名资深的：

* 全栈架构师
* Django 后端工程师
* Next.js 前端工程师
* 数据可视化工程师
* WebGL / Three.js 工程师
* UI/UX 设计师
* 网络监控系统设计师

从零设计并实现一个完整的：

# GLOBAL NETWORK INTELLIGENCE CENTER

全球网络智能监控中心。

这是一个用于展示真实服务器网络流量、网络连接、数据包、NAT、IP、端口、协议以及全球网络通信情况的实时数据可视化系统。

---

# 二、技术栈

## 后端

必须使用：

* Python
* Django
* Django REST Framework
* Django Channels
* WebSocket
* Redis

推荐：

```text
Django
├── Django REST Framework
├── Django Channels
├── Redis
└── PostgreSQL / SQLite
```

开发阶段允许 SQLite。

生产环境优先 PostgreSQL。

---

# 三、前端

必须使用：

* Next.js
* React
* TypeScript
* Tailwind CSS

推荐：

```text
Next.js
React
TypeScript
Tailwind CSS
```

地图 / 数据可视化：

优先考虑：

* Apache ECharts
* Three.js
* React Three Fiber
* WebGL

根据实际效果合理组合。

---

# 四、核心目标

最终系统用于实时展示：

```text
服务器
   ↓
iKuai Router
   ↓
Django Backend
   ↓
WebSocket
   ↓
Next.js
   ↓
Global Network Intelligence Center
```

用户打开页面后应该能够直观看到：

> 我的服务器现在正在和世界上哪些地方通信。

并能够进一步查看：

* 哪台内网设备
* 公网 IP
* 目标 IP
* 源端口
* 目标端口
* 协议
* 应用
* Domain
* 数据包方向
* 上传流量
* 下载流量
* NAT
* 连接状态
* 地理位置
* 网络节点
* 实时连接数量
* 网络流量趋势

---

# 五、非常重要：不要把它做成普通 Dashboard

最终视觉必须避免：

* 普通后台管理系统
* Bootstrap Admin
* Ant Design Dashboard
* 普通 BI
* 白色卡片
* 普通折线图
* 普通饼图
* 普通地图

视觉方向：

```text
Cyber Security
+
NOC
+
Network Operations Center
+
Mission Control
+
Cyberpunk
+
Futuristic HUD
+
Global Network Visualization
```

打开页面第一眼应该产生：

> 「这是一个正在实时监控全球网络基础设施的未来网络控制中心。」

---

# 六、整体视觉风格

采用：

## Dark Cyber / Futuristic HUD

主背景：

```text
#020611
#050B14
#08111F
```

主色：

```text
#00E5FF
#00B8FF
#00FFD5
```

辅助：

```text
#6C63FF
#8B5CF6
```

警告：

```text
#F59E0B
```

异常：

```text
#EF4444
```

整体：

* 深色
* 玻璃质感
* HUD
* 发光边框
* 微弱网格
* 粒子
* 数据流
* 扫描线
* 雷达
* 光点
* 网络节点
* 流光

但是一定要克制。

不能为了“科技感”堆大量动画。

---

# 七、页面视觉核心

整个页面的核心不是 Panel。

而是：

# 地图 + 网络流

地图应该占据页面大部分视觉面积。

整体布局：

```text
┌───────────────────────────────────────────────────────────────┐
│ GLOBAL NETWORK INTELLIGENCE CENTER                           │
│ SYSTEM ONLINE                     2026-08-26 01:29:32         │
├───────────────┬───────────────────────────────┬───────────────┤
│               │                               │               │
│ NETWORK       │                               │ REAL-TIME     │
│ METRICS       │                               │ MONITOR       │
│               │                               │               │
│ Traffic       │       GLOBAL / CHINA         │ Connections   │
│ Packets       │                               │ Protocols     │
│ Bandwidth     │       NETWORK FLOW            │ Threat        │
│ Connections   │                               │ Radar         │
│               │                               │               │
├───────────────┴───────────────────────────────┴───────────────┤
│                    REAL-TIME EVENT STREAM                     │
├───────────────────────────────────────────────────────────────┤
│ TRAFFIC │ COUNTRIES │ IP │ PORT │ APPLICATION │ PROTOCOL     │
└───────────────────────────────────────────────────────────────┘
```

不要机械地照着这个 ASCII 排版。

地图必须成为真正的视觉中心。

---

# 八、顶部 Header

顶部设计为未来科技 HUD。

左侧：

```text
◉ SYSTEM ONLINE
```

标题：

```text
GLOBAL NETWORK
INTELLIGENCE CENTER
```

副标题：

```text
REAL-TIME NETWORK TRAFFIC VISUALIZATION
```

中间：

```text
● LIVE
```

以及：

```text
2026-08-26 01:29:32
```

右侧：

```text
DATA STREAM
● CONNECTED
```

以及：

```text
iKuai
```

---

# 九、系统启动动画

第一次进入页面：

不要直接显示完整 Dashboard。

显示：

```text
INITIALIZING NETWORK CORE...

LOADING DJANGO API...
LOADING WEBSOCKET...
LOADING GEO ENGINE...
LOADING NETWORK NODES...
LOADING PACKET STREAM...

████████████████████ 100%

SYSTEM ONLINE
```

然后：

```text
Fade In
+
Map Zoom
+
Particle
+
Network Flow
```

进入主页面。

启动动画控制在约 1～2 秒。

不能影响正常使用。

---

# 十、核心地图系统

地图必须支持三个场景：

```text
GLOBAL
CHINA
LAN
```

顶部或者地图上方提供：

```text
[ GLOBAL ] [ CHINA ] [ LAN ]
```

---

# 十一、GLOBAL 场景

GLOBAL 场景用于展示：

```text
公网 ↔ 服务器
```

也就是：

```text
OUTBOUND
INBOUND
```

世界地图采用：

* 深色
* 极细国家边界
* 发光轮廓
* 深色海洋
* 微弱网格
* 粒子
* 数据流

禁止使用普通彩色政治地图。

---

# 十二、服务器核心节点

在地图上显示服务器核心。

例如：

```text
          ◉
       SERVER
    NETWORK CORE
```

设计成：

# CYBER CORE

包含：

* 内圈
* 外圈
* 旋转环
* Pulse
* Glow
* 扫描线
* 粒子
* 雷达

服务器在线：

```text
● ONLINE
```

异常：

```text
⚠ WARNING
```

---

# 十三、网络数据流

数据流必须是真实数据驱动。

例如：

```text
Tokyo
   ╲
    ╲
     ╲━━━━━━━━━━→ SERVER
```

或者：

```text
SERVER
   │
   └━━━━━━━━━━━━━━→ United States
```

线路使用：

* Bezier Curve
* Arc
* Great Circle

线路上有移动粒子。

---

# 十四、方向颜色

统一：

## OUTBOUND

```text
内网 → 公网
```

使用：

```text
Cyan / Blue
```

例如：

```text
10.0.1.2
    │
    └━━━━━━━━━━→ Cloudflare
```

---

## INBOUND

```text
公网 → 内网
```

使用：

```text
Purple / Magenta
```

例如：

```text
203.119.238.180
        │
        └━━━━━━━━━━→ 10.0.1.2
```

---

## INTERNAL

```text
内网 → 内网
```

使用：

```text
Green
```

但 INTERNAL 默认不要绘制到全球地图。

应该进入 LAN 场景。

---

# 十五、中国地图

CHINA 场景主要用于：

* 中国公网节点
* 中国城市
* 服务器位置
* 内网网络
* 中国境内数据流

显示省份边界。

重点城市可以根据真实数据动态出现。

例如：

```text
北京
上海
广州
深圳
杭州
成都
重庆
武汉
```

不要强制显示没有数据的城市。

---

# 十六、LAN 场景

这是项目非常重要的一部分。

LAN 用于展示真实内网设备之间的通信。

例如：

```text
                     iKuai Router
                          │
              ┌───────────┼───────────┐
              │           │           │
              ▼           ▼           ▼

          10.0.1.2     10.0.1.10    10.0.1.20
            PC           DNS          Server
```

节点之间有真实数据流。

例如：

```text
10.0.1.10
     │
     └────────→ 192.168.2.1:53
```

---

# 十七、后端真实数据结构

目前 Django 后端可以获得类似以下数据：

```json
{
  "id": "pkt_001",
  "timestamp": 1712450000,
  "direction": "outbound",
  "app_name": "Cloudflare",
  "protocol": "tcp",
  "status": "请求连接",

  "source": {
    "ip": "10.0.1.2",
    "port": 40786,
    "domain": null,
    "lat": 39.9042,
    "lng": 116.4074
  },

  "destination": {
    "ip": "162.159.61.8",
    "port": 443,
    "domain": "dns.cloudflare.com",
    "lat": 37.7749,
    "lng": -122.4194
  },

  "nat_info": {
    "forward_addr": "10.0.1.2",
    "src_port": 40786,
    "dst_port": 443
  },

  "total_up": 60,
  "total_down": 0
}
```

后端未来可能修改字段。

因此：

# 前端绝对不能直接依赖这个 JSON。

---

# 十八、Django 数据 Adapter

后端或者前端都必须设计数据适配层。

推荐：

```text
Backend Raw Data
      ↓
Normalizer / Adapter
      ↓
Normalized NetworkFlow
      ↓
Visualization
```

推荐统一类型：

```typescript
interface NetworkFlow {
  id: string;

  timestamp: number;

  direction:
    | "outbound"
    | "inbound"
    | "internal";

  source: {
    ip: string;
    port: number;
    domain?: string | null;
    lat?: number | null;
    lng?: number | null;
  };

  destination: {
    ip: string;
    port: number;
    domain?: string | null;
    lat?: number | null;
    lng?: number | null;
  };

  application: string;

  protocol: string;

  status?: string | null;

  bytes: {
    upload: number;
    download: number;
    total: number;
  };

  nat?: {
    forwardAddress?: string;
    sourcePort?: number;
    destinationPort?: number;
    originalDestination?: string;
  };
}
```

---

# 十九、数据方向

目前后端提供：

```text
outbound
inbound
internal
```

优先使用后端已经判断好的：

```text
direction
```

前端不要重复猜测方向。

---

# 二十、Outbound

定义：

```text
内网设备 → 公网
```

例如：

```text
10.0.1.2
      ↓
162.159.61.8
```

视觉：

```text
中国 / 内网
      │
      └━━━━━━━━━━━━━━→ 公网节点
```

---

# 二十一、Inbound

定义：

```text
公网 → 内网
```

例如：

```text
203.119.238.180
        ↓
10.0.1.2:445
```

注意：

公网来源：

```text
source.ip
```

NAT：

```text
nat_info.forward_addr
```

端口：

```text
nat_info.src_port
nat_info.dst_port
```

如果存在：

```text
original_dst
```

也必须保留。

---

# 二十二、Internal

定义：

```text
内网 A → 内网 B
```

例如：

```text
10.0.1.10
      ↓
192.168.2.1
```

必须进入 LAN 场景。

不要将：

```text
10.0.1.10
```

错误显示到全球地图。

---

# 二十三、Private IP 判断

实现：

```typescript
isPrivateIP(ip)
```

支持：

```text
10.0.0.0/8
172.16.0.0/12
192.168.0.0/16
```

Private IP：

不能进行公网 GeoIP 定位。

---

# 二十四、Geo 数据

目前后端已经可以提供：

```text
lat
lng
```

优先使用后端提供的坐标。

不要前端再次查询 GeoIP。

如果未来需要 GeoIP：

应该通过 Django 服务端统一处理。

前端只接收：

```text
lat
lng
country
city
region
```

---

# 二十五、Django API

设计 REST API。

例如：

```text
/api/network/overview/
/api/network/packets/
/api/network/flows/
/api/network/stats/
/api/network/countries/
/api/network/protocols/
/api/network/applications/
/api/network/connections/
/api/network/events/
```

具体 API 可以根据实际需求调整。

---

# 二十六、WebSocket

核心实时数据必须使用：

# Django Channels + WebSocket

例如：

```text
ws://server/ws/network/
```

实时推送：

```json
{
  "type": "packet",
  "data": {
    ...
  }
}
```

---

# 二十七、WebSocket Event 类型

设计成可扩展：

```text
packet
connection
traffic
status
alert
heartbeat
```

例如：

```json
{
  "type": "packet",
  "data": {}
}
```

未来增加：

```text
alert
```

不需要修改整个前端架构。

---

# 二十八、Redis

Django Channels 使用 Redis 作为 Channel Layer。

推荐：

```text
iKuai
  ↓
Django
  ↓
Redis
  ↓
Django Channels
  ↓
WebSocket
  ↓
Next.js
```

---

# 二十九、Next.js 架构

建议：

```text
app/
├── page.tsx
├── layout.tsx
│
├── dashboard/
│
├── api/
│
components/
├── dashboard/
├── map/
├── globe/
├── china/
├── lan/
├── network-flow/
├── server-core/
├── radar/
├── charts/
├── events/
├── panels/
└── hud/
│
hooks/
├── useNetworkSocket.ts
├── useNetworkStats.ts
├── usePacketStream.ts
└── useMapScene.ts
│
lib/
├── api/
├── adapters/
├── formatters/
├── network/
└── utils/
│
store/
└── networkStore.ts
│
types/
└── network.ts
```

---

# 三十、Next.js Rendering 策略

由于地图、Three.js、ECharts 等属于客户端可视化：

需要合理使用：

```text
"use client"
```

避免服务端渲染 WebGL。

可以：

```text
Server Components
        ↓
数据 / Layout
        ↓
Client Components
        ↓
WebGL / Map / Charts
```

不要把整个项目无脑变成 Client Component。

---

# 三十一、状态管理

可以使用：

```text
Zustand
```

或者其他轻量状态管理。

统一维护：

```text
network status
packets
flows
connections
traffic
countries
protocols
events
current scene
selected flow
time range
```

---

# 三十二、实时数据处理

WebSocket 收到数据：

```text
WebSocket
   ↓
Adapter
   ↓
Validation
   ↓
Store
   ↓
Aggregation
   ↓
Visualization
```

不要：

```text
WebSocket
   ↓
直接 setState
   ↓
整个页面重渲染
```

---

# 三十三、性能

必须考虑：

## 60 FPS

尤其是：

* 地图
* Arc
* Particle
* Glow
* Radar
* 数据流

尽量使用：

```text
Canvas
WebGL
requestAnimationFrame
```

避免：

```text
大量 DOM
大量 React Component
```

---

# 三十四、实时数据限流

如果后端每秒产生几百甚至几千条数据：

前端不能每条数据都触发一次 React Render。

使用：

```text
Batch Update
Throttle
Debounce
requestAnimationFrame
```

例如：

```text
WebSocket
   ↓
Buffer
   ↓
每 50～100ms
批量提交
   ↓
Visualization
```

---

# 三十五、数据缓存

前端只保存有限数据。

例如：

```text
最近 5000 条事件
```

超过：

```text
删除旧数据
```

不能无限增长。

---

# 三十六、实时统计

根据真实数据计算：

```text
Total Traffic
Upload
Download
Packets
Connections
Protocols
Applications
Countries
```

---

# 三十七、Traffic Panel

左侧显示：

```text
NETWORK TRAFFIC

↑ 8.42 Gbps
↓ 5.31 Gbps
```

同时：

```text
TOTAL
13.73 Gbps
```

使用动态数字。

---

# 三十八、Packets

```text
PACKETS

128,492

OUTBOUND
72,391

INBOUND
38,291

INTERNAL
17,810
```

---

# 三十九、Connections

显示：

```text
ACTIVE CONNECTIONS

18,294
```

如果暂时没有真实 Connection ID：

可以使用：

```text
source IP
source port
destination IP
destination port
protocol
```

生成临时 connection key。

---

# 四十、Protocol

根据真实：

```text
protocol
```

动态统计。

例如：

```text
TCP
UDP
QUIC
HTTP
HTTPS
DNS
```

不要写死。

---

# 四十一、Application

根据：

```text
app_name
```

动态统计：

```text
Cloudflare
DNS
SMB
SSH
HTTP
HTTPS
```

---

# 四十二、实时事件流

底部：

# REAL-TIME NETWORK EVENTS

例如：

```text
01:29:32  INFO
10.0.1.2 → 162.159.61.8
TCP / 443
60 B
```

或者：

```text
01:29:31  INBOUND
203.119.238.180 → 10.0.1.2
TCP / 445
4.32 KB
```

日志自动滚动。

---

# 四十三、点击事件

点击任何数据流：

打开：

# CONNECTION DETAILS

显示：

```text
SOURCE
10.0.1.2:40786

DESTINATION
162.159.61.8:443

APPLICATION
Cloudflare

PROTOCOL
TCP

STATUS
请求连接

UPLOAD
60 B

DOWNLOAD
0 B
```

如果有 NAT：

```text
NAT

Forward Address
10.0.1.2

Source Port
40786

Destination Port
443
```

---

# 四十四、Inbound NAT 展示

例如：

```text
PUBLIC SOURCE
203.119.238.180:57584

        ↓

NAT

        ↓

192.168.2.158

        ↓

INTERNAL TARGET

10.0.1.2:445
```

设计成视觉化的 NAT Pipeline。

这是系统非常重要的功能。

---

# 四十五、国家统计

根据真实 Geo 数据：

```text
TOP COUNTRIES
```

动态生成。

例如：

```text
United States
China
Japan
Singapore
Germany
```

不要预设固定国家。

没有数据的国家不要显示。

---

# 四十六、IP 排名

显示：

```text
TOP SOURCE IP
```

动态统计。

使用：

```text
IP
Packets
Traffic
Connections
```

---

# 四十七、Port 排名

显示：

```text
TOP PORTS
```

例如：

```text
443
80
53
22
445
8080
8443
```

动态生成。

---

# 四十八、Network Radar

右上角设计一个：

# NETWORK RADAR

持续扫描。

真实网络节点出现时：

```text
Radar Scan
     ↓
Node Detected
     ↓
Pulse
     ↓
Network Flow
```

不要纯随机生成假节点。

---

# 四十九、Threat Monitor

设计：

# NETWORK HEALTH

例如：

```text
NETWORK HEALTH

98.7%
```

以及：

```text
NORMAL
WARNING
CRITICAL
```

如果未来 Django 后端提供异常检测：

可以实时显示。

目前没有真实 Threat 数据时：

不要伪造真实攻击。

可以只展示：

```text
ANOMALY DETECTION
```

并明确标记为：

```text
SIMULATION
```

或者暂时隐藏。

---

# 五十、数据流强度

根据：

```text
total_up
total_down
```

计算：

```text
flow intensity
```

影响：

* 线宽
* Glow
* 粒子
* 动画速度

必须归一化。

不能直接使用 bytes 作为 CSS 或 WebGL 参数。

---

# 五十一、数据包动画生命周期

```text
RECEIVED
 ↓
CREATED
 ↓
ANIMATING
 ↓
COMPLETED
 ↓
REMOVED
```

动画结束后删除。

但是统计数据保留。

---

# 五十二、流量聚合

如果短时间内：

```text
10.0.1.2 → 162.159.61.8
```

出现几十次：

不要画几十条完全重叠的线。

聚合：

```text
Connections
Packets
Traffic
```

显示：

```text
10.0.1.2
       │
       │ 128 packets
       │ 24.8 MB
       ▼
162.159.61.8
```

---

# 五十三、Global Flow

可以按照：

```text
Source Location
Destination Location
```

进行聚合。

例如：

```text
China
   │
   ├────→ United States
   │
   ├────→ Japan
   │
   └────→ Singapore
```

---

# 五十四、地图交互

鼠标 Hover 国家：

```text
UNITED STATES

Traffic
2.84 TB

Packets
8,294,183

Connections
12,492
```

Hover 节点：

```text
TOKYO

Packets
82,391

Traffic
824 GB

Latency
42 ms
```

Hover 数据流：

```text
SOURCE
Tokyo

DESTINATION
Server

PROTOCOL
HTTPS

TRAFFIC
42.8 MB
```

所有 Tooltip 都使用 HUD 风格。

---

# 五十五、地图场景动画

Global → China：

```text
GLOBAL
 ↓
ZOOM IN
 ↓
CHINA
```

China → LAN：

```text
CHINA
 ↓
ZOOM / FADE
 ↓
LAN NETWORK
```

不要刷新整个页面。

---

# 五十六、内网设备

如果后端未来提供设备信息：

支持：

```text
hostname
mac
ip
device_type
vendor
```

当前没有则只显示：

```text
IP
```

不要伪造：

```text
MAC
hostname
device vendor
```

---

# 五十七、时间窗口

支持：

```text
5S
30S
1M
5M
15M
1H
```

用于：

* Traffic
* Packets
* Connections
* Countries
* Protocols

---

# 五十八、异常处理

WebSocket 断开：

```text
● DATA STREAM DISCONNECTED

RECONNECTING...
```

恢复：

```text
● DATA STREAM CONNECTED
```

Django API 失败：

显示：

```text
API CONNECTION ERROR
```

但不能让整个页面崩溃。

---

# 五十九、Loading

每个大型数据组件应该有自己的 Loading State。

例如：

```text
LOADING GEO DATA...
```

不要整个页面一直显示 Loading。

---

# 六十、空数据

如果当前没有网络数据：

不要显示：

```text
0
0
0
```

造成“系统坏了”的感觉。

应该：

```text
WAITING FOR NETWORK DATA...

NO ACTIVE FLOWS
```

地图显示：

```text
SYSTEM ONLINE
WAITING FOR TRAFFIC
```

---

# 六十一、错误数据

后端可能存在：

```text
null
--
空字符串
非法 IP
缺失坐标
缺失 domain
```

前端必须容错。

任何一条异常数据不能导致：

```text
React crash
WebGL crash
Map crash
```

---

# 六十二、Django 后端目录建议

```text
backend/
├── manage.py
│
├── config/
│   ├── settings.py
│   ├── urls.py
│   ├── asgi.py
│   └── routing.py
│
├── network/
│   ├── models.py
│   ├── serializers.py
│   ├── views.py
│   ├── consumers.py
│   ├── routing.py
│   ├── services.py
│   ├── adapters.py
│   └── urls.py
│
├── analytics/
│   ├── services.py
│   ├── aggregators.py
│   └── serializers.py
│
└── core/
```

---

# 六十三、Django Services

不要把所有业务逻辑写到 View。

使用：

```text
services.py
aggregators.py
adapters.py
```

例如：

```text
PacketService
TrafficAggregationService
ConnectionService
GeoService
NetworkStatisticsService
```

---

# 六十四、Django Models

模型需要考虑：

```text
Packet
Connection
NetworkNode
TrafficSnapshot
```

但不要为了“完整”而过度设计数据库。

如果真实 iKuai 数据是实时流：

可以：

```text
Redis
+
短期数据库
```

保存实时数据。

历史数据再进入 PostgreSQL。

---

# 六十五、实时数据架构

推荐：

```text
iKuai
  │
  ▼
Django Collector
  │
  ├──────────────→ Redis
  │
  ▼
Normalizer
  │
  ▼
Aggregator
  │
  ▼
Django Channels
  │
  ▼
WebSocket
  │
  ▼
Next.js
```

---

# 六十六、前后端数据契约

WebSocket 消息统一：

```json
{
  "type": "packet",
  "timestamp": 1712450000,
  "data": {}
}
```

未来：

```json
{
  "type": "alert",
  "timestamp": 1712450000,
  "data": {}
}
```

```json
{
  "type": "traffic",
  "timestamp": 1712450000,
  "data": {}
}
```

保持协议可扩展。

---

# 六十七、Mock 模式

必须提供：

```text
DEVELOPMENT MOCK MODE
```

但是 Mock 数据必须严格模拟真实 Django 数据。

架构：

```text
Mock Backend Packet
       ↓
Adapter
       ↓
NetworkFlow
       ↓
UI
```

不能设计第二套 UI 数据。

---

# 六十八、真实模式

生产：

```text
NEXT_PUBLIC_API_URL
NEXT_PUBLIC_WS_URL
```

例如：

```text
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXT_PUBLIC_WS_URL=ws://localhost:8000/ws/network/
```

具体环境变量名称可以根据项目规范调整。

---

# 六十九、安全

不要：

* 将 Django Secret Key 放到 Next.js
* 将 Redis 暴露给浏览器
* 将数据库连接暴露给前端
* 将 iKuai 管理接口直接暴露给浏览器

正确：

```text
Browser
 ↓
Next.js
 ↓
Django
 ↓
iKuai
```

---

# 七十、CORS / CSRF

Django 必须正确配置：

```text
CORS
CSRF
Allowed Hosts
WebSocket Origin
```

开发环境与生产环境分离。

---

# 七十一、生产部署

最终应该支持：

```text
                    Internet
                       │
                       ▼
                    Nginx
                   /      \
                  /        \
                 ▼          ▼
             Next.js      Django
                            │
                     ┌──────┴──────┐
                     ▼             ▼
                   Redis       PostgreSQL
                     │
                     ▼
                   iKuai
```

---

# 七十二、Nginx

生产环境：

```text
/             → Next.js
/api/         → Django
/ws/          → Django Channels
```

WebSocket 必须正确支持：

```text
Upgrade
Connection
```

---

# 七十三、项目工程质量

要求：

* TypeScript 严格模式
* ESLint
* Prettier
* Python formatting
* Django migration
* 类型定义
* API schema
* 环境变量
* 错误处理
* 日志
* README

---

# 七十四、组件设计

至少拆分：

```text
Dashboard
Header
GlobalMap
ChinaMap
LanTopology
ServerCore
NetworkFlow
NetworkRadar
TrafficChart
ProtocolStats
CountryStats
IpRanking
PortRanking
ApplicationStats
EventStream
ThreatMonitor
ConnectionDetails
HudPanel
StatusIndicator
```

---

# 七十五、视觉组件

不要让每个组件自己随意写颜色。

建立统一：

```text
Cyber Theme
```

统一：

* Colors
* Glow
* Border
* Typography
* Spacing
* Animation
* Shadows

---

# 七十六、字体

推荐：

```text
Inter
Space Grotesk
JetBrains Mono
Orbitron
```

数字：

```text
JetBrains Mono
```

---

# 七十七、背景

加入：

```text
Grid
Noise
Scanline
Particle
Glow
```

但是所有背景动画必须尽可能 GPU 加速。

---

# 七十八、响应式

重点支持：

```text
1920 × 1080
2560 × 1440
3840 × 2160
```

同时兼容：

```text
1366 × 768
1440 × 900
```

16:9 是主要目标。

---

# 七十九、禁止事项

绝对不要：

❌ 做成普通后台

❌ 使用大量白色 Card

❌ 使用默认 ECharts 样式

❌ 使用默认地图样式

❌ 随机伪造真实网络流量

❌ 随机伪造真实 IP

❌ 随机伪造国家

❌ 将私有 IP 显示成公网地理位置

❌ 将真实数据和 Mock 数据同时运行

❌ 把 packet 当 connection

❌ 把 internal 流量画成全球流量

❌ 前端重新判断后端已经确定的 direction

❌ 无限缓存实时数据

❌ 让每个 WebSocket 消息触发整个页面 Render

---

# 八十、最终页面结构

最终希望形成：

```text
┌─────────────────────────────────────────────────────────────┐
│ GLOBAL NETWORK INTELLIGENCE CENTER                          │
│ SYSTEM ONLINE              LIVE              DATA CONNECTED │
├──────────────┬────────────────────────────────┬─────────────┤
│              │                                │             │
│ NETWORK      │                                │ NETWORK     │
│ METRICS      │         GLOBAL MAP             │ RADAR       │
│              │                                │             │
│ Traffic      │       ✦ ━━━━━→ ✦              │ Protocol    │
│ Packets      │    ╱                            │ Connections │
│ Bandwidth    │  SERVER                         │ Health      │
│ Connections  │    ╲                            │             │
│              │       ━━━━━━━→ ✦               │             │
│              │                                │             │
├──────────────┴────────────────────────────────┴─────────────┤
│ REAL-TIME NETWORK EVENTS                                    │
├─────────────────────────────────────────────────────────────┤
│ COUNTRIES │ IP │ PORT │ APPLICATION │ PROTOCOL │ TRAFFIC    │
└─────────────────────────────────────────────────────────────┘
```

---

# 八十一、最终体验

用户打开页面：

第一眼：

> 巨大的全球地图。

第二眼：

> 服务器核心节点。

第三眼：

> 全球数据流正在不断移动。

第四眼：

> 实时数据不断变化。

第五眼：

> 点击任何一条数据流，可以看到完整连接详情。

第六眼：

> 切换 CHINA，可以查看中国区域网络。

第七眼：

> 切换 LAN，可以查看真实内网设备拓扑。

最终感觉：

# 「这是我的服务器正在运行的全球网络。」

而不是：

# 「这是一个网页 Dashboard。」

---

# 八十二、最终开发顺序

不要一次性生成所有功能。

按照以下顺序实现：

## Phase 1

搭建：

```text
Django
Next.js
Redis
PostgreSQL
```

确保前后端可以正常通信。

---

## Phase 2

实现：

```text
Django REST API
Django Channels
WebSocket
```

先发送 Mock Packet。

---

## Phase 3

实现：

```text
Next.js
WebSocket Client
Zustand
Adapter
```

确保实时数据能够进入 Store。

---

## Phase 4

实现：

```text
Global Map
Server Core
Network Flow
```

优先把地图视觉效果做好。

---

## Phase 5

实现：

```text
China Map
LAN Topology
```

---

## Phase 6

实现：

```text
Traffic
Packets
Connections
Protocol
Country
IP
Port
Application
```

---

## Phase 7

实现：

```text
Connection Details
NAT Visualization
Event Stream
Radar
```

---

## Phase 8

实现：

```text
Performance Optimization
WebGL Optimization
Memory Management
Error Handling
```

---

## Phase 9

接入真实 iKuai 数据。

此时：

```text
Mock
```

自动关闭。

---

# 八十三、最终验收标准

## 视觉

* [ ] 第一眼具有强烈科技感
* [ ] Cyber Security / NOC 风格明显
* [ ] 地图是视觉中心
* [ ] 数据流非常明显
* [ ] HUD 设计统一
* [ ] 动画流畅
* [ ] 不像普通后台

## 地图

* [ ] GLOBAL
* [ ] CHINA
* [ ] LAN
* [ ] 平滑切换
* [ ] 数据流
* [ ] 节点
* [ ] Hover
* [ ] Zoom
* [ ] Particle

## 数据

* [ ] Outbound
* [ ] Inbound
* [ ] Internal
* [ ] Packet
* [ ] Connection
* [ ] Traffic
* [ ] Protocol
* [ ] Application
* [ ] IP
* [ ] Port
* [ ] NAT
* [ ] Status
* [ ] Geo

## 后端

* [ ] Django
* [ ] DRF
* [ ] Channels
* [ ] Redis
* [ ] WebSocket
* [ ] API
* [ ] Adapter
* [ ] Aggregation

## 前端

* [ ] Next.js
* [ ] React
* [ ] TypeScript
* [ ] Tailwind
* [ ] Zustand
* [ ] ECharts / Three.js
* [ ] WebGL
* [ ] 60 FPS
* [ ] 错误处理
* [ ] WebSocket 重连

## 工程

* [ ] Mock 模式
* [ ] Real 模式
* [ ] 环境变量
* [ ] Docker 可选
* [ ] Nginx 部署
* [ ] README
* [ ] Migration
* [ ] ESLint
* [ ] TypeScript Strict

---

# 八十四、最重要的最终要求

请不要把这个项目理解为：

> 「做一个好看的数据大屏。」

而应该理解为：

> **「构建一个基于 Django + Next.js + WebSocket 的实时全球网络态势感知系统。」**

视觉只是第一层。

底层必须具备：

```text
真实网络数据
        ↓
Django
        ↓
数据标准化
        ↓
Redis
        ↓
WebSocket
        ↓
Next.js
        ↓
实时聚合
        ↓
全球地图
        ↓
中国地图
        ↓
LAN 拓扑
        ↓
实时网络态势
```

最终目标：

# GLOBAL NETWORK INTELLIGENCE CENTER

**Real Network Data · Real-time Visualization · Global Network Awareness**
