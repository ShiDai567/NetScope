# NetScope

NetScope 是一个网络数据包流转可视化项目，用科幻风格的世界/中国地图界面展示服务端与客户端之间的数据包传输过程。项目采用前后端分离结构：前端负责地图渲染、粒子动画与实时统计，后端提供模拟数据包引擎，并支持接入真实 iKuai 路由器作为数据源。

## 项目特点

- 世界地图 + 中国地图双视图切换，科幻风格暗色主题
- 三种节点类型：外网服务器（红色）、公网客户端（蓝色）、内网设备（绿色）
- 数据包粒子动画：按方向区分外弧线/内弧线/直线，状态颜色实时切换
- TCP 状态机可视化：等待连接（呼吸闪烁）→ 请求连接（快速跳动）→ 已连接（稳定流动+拖尾）→ 关闭连接（渐隐）
- UDP / ICMP 无状态流，支持丢包/高延迟标记
- NAT 转换可视化：虚线显示地址转换路径，端口映射场景展示 original_dst
- 实时控制面板：方向 / 协议 / 应用三级筛选
- 统计面板：连接计数、方向分布、协议饼图、带宽趋势、延迟热力图、丢包率
- 时间轴回放：支持 0.5x / 1x / 2x / 5x 倍速播放历史数据
- iKuai 路由器直连：通过内置 SDK 登录爱快面板，拉取真实终端连接数据

## 技术栈

### 前端

- Next.js 15 + React 19 + TypeScript
- Tailwind CSS v4
- ECharts 5（地图 + 统计图表）
- Three.js（星空背景）
- Phosphor Icons
- Geist / Geist Mono 字体

### 后端

- Python 3.13 + Django 5.2
- 内置 iKuai SDK（标准库实现，零第三方依赖）
- SQLite（最小化配置，运行态数据在内存中）

## 项目结构

```text
NetScope/
├── AGENTS.md                  # 开发规范与需求文档
├── README.md                  # 本文件
├── sdk/                       # iKuai Python SDK（可复用）
│   └── ikuai_sdk/
│       ├── client.py
│       ├── models.py
│       └── exceptions.py
├── backend/                   # Django 后端
│   ├── config/                # 项目配置
│   ├── traffic/               # 核心应用
│   │   ├── simulation.py      # 模拟引擎
│   │   ├── ikuai.py           # iKuai 轮询器
│   │   ├── hub.py             # 全局状态中枢
│   │   ├── stats.py           # 统计聚合器
│   │   ├── packets.py         # 数据包方向判断与标准化
│   │   ├── geo.py             # IP 地理位置工具
│   │   ├── views.py           # API 视图
│   │   └── tests.py           # 单元测试
│   ├── manage.py
│   └── requirements.txt
└── frontend/                  # Next.js 前端
    ├── public/maps/           # GeoJSON 地图数据
    ├── src/
    │   ├── app/               # 页面入口
    │   ├── components/        # 可视化组件
    │   ├── state/             # 数据流状态管理
    │   └── lib/               # 工具函数与类型
    └── package.json
```

## 本地运行

### 1. 安装依赖

后端：

```bash
cd backend
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

前端：

```bash
cd frontend
npm install
```

### 2. 启动后端

```bash
cd backend
.venv/bin/python manage.py runserver 0.0.0.0:4000 --noreload
```

后端默认运行在 `http://localhost:4000`。

### 3. 启动前端

```bash
cd frontend
npm run dev
```

前端默认运行在 `http://localhost:3000`。

启动后，前端会自动轮询后端接口获取数据包事件，并渲染为地图上的动态传输效果。

## API 说明

| 接口 | 方法 | 说明 |
|---|---|---|
| `GET /api/health` | 健康检查 | |
| `GET /api/packets?since=<seq>` | 增量数据包事件 | seq 之后的新事件 |
| `GET /api/history?minutes=5` | 历史事件 | 用于时间轴回放 |
| `GET /api/devices` | 内网设备列表 | IP / MAC / 连接数 / 速率 |
| `GET /api/nodes` | 公网节点列表 | 服务器 + 客户端 |
| `GET /api/stats` | 实时统计 | 连接数 / 带宽 / 延迟 / 丢包率 |
| `GET /api/mode` | 当前数据源模式 | simulation / ikuai |
| `POST /api/ikuai/connect` | 连接 iKuai | `{routerUrl, username, password}` |
| `POST /api/ikuai/disconnect` | 断开 iKuai | 恢复模拟数据 |

## 接入真实 iKuai 路由器

1. 点击页面右上角设置图标
2. 填写路由器地址、用户名、密码
3. 点击"连接 iKuai"
4. 成功后，页面左上角模式标签变为"iKuai 直连"

断开连接后自动恢复模拟数据。

## 开发说明

- 前端页面核心入口：`frontend/src/app/page.tsx`
- 样式定义：`frontend/src/app/globals.css`
- 后端模拟引擎：`backend/traffic/simulation.py`
- iKuai SDK：`sdk/ikuai_sdk/`
- 运行环境变量示例见 `backend/.env.example`

## 测试

后端单元测试：

```bash
cd backend
.venv/bin/python manage.py test traffic -v 2
```

## 适用场景

- 网络流量演示
- 安全可视化大屏
- 教学或汇报展示
- 网络监控原型验证

## License

MIT
