# NetScope 网络数据包可视化 - 开发规范

- **版本**: v1.0
- **日期**: 2024
- **作者**: AI Agent

---

## 角色设定

你现在是一位资深的全栈开发工程师和数据可视化专家，精通交互设计、前端动画和后端代码的编写。

## 任务目标

请帮我编写一个"网络数据包收发（Network Packet Flow）"的可视化组件/页面和后端程序。

## 前端技术栈

请使用包括但不限于 **Next.js + ECharts + Three.js** 来实现，使用 `design-taste-frontend` skill 技能作为前端规范。

## 后端技术栈

请使用包括但不限于 **Python + Django**，iKuai 部分使用 SDK 来获取每个设备的数据包信息。

## 核心视觉与动画要求

### 1. 节点展示（Nodes）

- 使用科幻风格地图作为背景，有世界地图和中国地图两个视图可以选择
- 节点按网络位置分类：
  - 🔴 **外网服务器**（公网IP）：地图上标注真实地理位置，使用红色发光节点
  - 🟢 **内网设备**（10.0.1.x/192.168.x.x）：鼠标移动到内网设备节点上，能展示出来该设备的详细信息（IP、MAC、设备名称等）
  - 🔵 **公网客户端**（访问内网的来源）：使用蓝色发光节点
- 节点大小根据设备活跃度（连接数）动态变化

### 2. 数据包动画（Animations）

   - 数据包用粒子/光点表示，大小根据 `total_up + total_down` 流量动态缩放
   - **方向轨迹**：

     - 向外发包（outbound）：从内网节点 → 外弧线 → 外网服务器，带→箭头
     - 向内接受（inbound）：从外网客户端 → 内弧线 → 内网节点，带←箭头
     - 内网通信（internal）：内网节点间直线连接，带↔双向箭头
   - **连接状态动画**：

     - `等待连接`：粒子闪烁（黄色呼吸灯效果）
     - `请求连接`：粒子快速跳动
     - `已连接`：粒子稳定流动，带拖尾光效
     - `关闭连接`：粒子渐隐消失
3. **状态颜色（Colors）**：

   - 🟢 绿色：发送/接收成功（status = 已连接）
   - 🔴 红色：丢包/连接失败（到达半路消失或爆炸特效）
   - 🟡 黄色：高延迟/等待中（status = 等待连接/请求连接，移动速度变慢并闪烁）
   - ⚪ 灰色：连接关闭（status = 关闭连接，粒子淡出）

   相同的包随着时间变化连接状态发生变化时，应该能丝滑切换
4. **协议与应用区分（Protocols & Apps）**：

   - **协议颜色**：TCP（蓝色）、UDP（绿色）、ICMP（黄色）
   - 鼠标悬停显示 `app_name` 和协议类型

### 5. NAT 可视化

   - 显示 NAT 转换过程：内网IP → 路由器NAT → 公网IP
   - 用虚线连接 `nat_info.forward_addr` 显示地址转换路径
   - 端口映射场景显示 `original_dst` 原始目标

## 互动要求

### 1. 实时控制面板

   - 提供方向筛选按钮：【全部】【向外发包】【向内接受】【内网通信】
   - 提供协议筛选：TCP / UDP / ICMP
   - 提供应用筛选：DNS / SMB / SSL / HTTP / 其他
2. **数据包交互**：

   - 鼠标悬停（Hover）在移动的数据包上时：
     - 暂停该数据包动画
     - 弹出 Tooltip 显示详细信息：
       - 源 IP:Port → 目的 IP:Port
       - 协议类型、应用名称 (`app_name`)
       - 连接状态 (`status`)
       - Payload 大小：`total_up` ↑ / `total_down` ↓
       - NAT 信息：`forward_addr` 地址转换
       - 时间戳
   - 点击数据包：锁定跟踪视角，高亮显示该连接的完整路径
3. **统计面板**（实时更新）：

   - 总连接数 / 活跃连接数 / 已关闭连接数
   - 方向分布：向外发包数 / 向内接受数 / 内网通信数
   - 协议分布：TCP / UDP / ICMP 占比
   - 流量统计：总上传 ↑ / 总下载 ↓（实时带宽）
   - 丢包率 / 延迟热力图
4. **时间轴回放**：

   - 提供时间滑块，可回放历史数据包流动
   - 支持倍速播放（0.5x / 1x / 2x / 5x）

## 数据结构参考

请基于以下 JSON 结构来驱动你的动画逻辑：

> **status 字段说明**：
> - UDP 状态：`null`、`"--"` 或省略（UDP 无连接状态）
> - TCP 状态：`"等待连接"`、`"请求连接"`、`"已连接"`、`"关闭连接"`

## 数据包方向判断逻辑

根据真实 iKuai 路由器数据，连接记录包含以下字段：

- `dst_addr`: 目标地址（可能是内网或公网）
- `forward_addr`: NAT 转发地址（经过路由器转换后的地址）
- `src_port`: 源端口（内网设备端口）
- `dst_port`: 目标端口
- `interface`: 接口（wan1=外网, lan1=内网）

### 判断规则

1. **向外发包**（内网设备 -> 公网）：`dst_addr` 是公网IP，`forward_addr` 是内网IP（NAT后的源地址）
2. **外部接受**（公网 -> 内网设备）：`dst_addr` 是内网IP（端口转发目标），`forward_addr` 是公网IP（真实来源）
3. **内网通信**（内网 <-> 内网）：`dst_addr` 和 `forward_addr` 都是内网IP

### Source/Destination 映射规则

- **向外发包**: source=内网设备, destination=公网服务器
- **外部接受**: source=公网客户端, destination=内网设备（端口转发目标）
- **内网通信**: source=内网设备A, destination=内网设备B

向外部发数据包示例（内网设备 10.0.1.2 访问 Cloudflare DNS）：

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

向内网发数据包示例（内网设备 10.0.1.10 查询内网 DNS 服务器）：

```json
{
  "id": "pkt_002",
  "timestamp": 1712450000,
  "direction": "internal",
  "app_name": "DNS",
  "protocol": "udp",
  "status": "--",
  "source": { 
    "ip": "10.0.1.10", 
    "port": 38338, 
    "domain": null, 
    "lat": 39.9042, 
    "lng": 116.4074 
  },
  "destination": { 
    "ip": "192.168.2.1", 
    "port": 53, 
    "domain": null, 
    "lat": 39.9042, 
    "lng": 116.4074 
  },
  "nat_info": {
    "forward_addr": "10.0.1.1",
    "src_port": 38338,
    "dst_port": 53
  },
  "total_up": 63,
  "total_down": 0
}
```

从外部接受数据包示例（公网访问内网 SMB 服务，端口转发）：

```json
{
  "id": "pkt_003",
  "timestamp": 1712450000,
  "direction": "inbound",
  "app_name": "SMB",
  "protocol": "tcp",
  "status": "已连接",
  "source": { 
    "ip": "203.119.238.180", 
    "port": 57584, 
    "domain": null, 
    "lat": 39.9042, 
    "lng": 116.4074 
  },
  "destination": { 
    "ip": "10.0.1.2", 
    "port": 445, 
    "domain": null, 
    "lat": 39.9042, 
    "lng": 116.4074 
  },
  "nat_info": {
    "forward_addr": "203.119.238.180",
    "src_port": 57584,
    "dst_port": 445,
    "original_dst": "192.168.2.158"
  },
  "total_up": 2225,
  "total_down": 2156
}
```

从内网接受数据包示例（DNS 服务器响应查询）：

```json
{
  "id": "pkt_004",
  "timestamp": 1712450000,
  "direction": "internal",
  "app_name": "DNS",
  "protocol": "udp",
  "status": null,
  "source": { 
    "ip": "10.0.1.1", 
    "port": 53, 
    "domain": null, 
    "lat": 39.9042, 
    "lng": 116.4074 
  },
  "destination": { 
    "ip": "10.0.1.10", 
    "port": 38338, 
    "domain": null, 
    "lat": 39.9042, 
    "lng": 116.4074 
  },
  "nat_info": {
    "forward_addr": "10.0.1.1",
    "src_port": 53,
    "dst_port": 38338
  },
  "total_up": 63,
  "total_down": 0
}
```
