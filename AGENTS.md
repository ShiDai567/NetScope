**【角色设定】**
你现在是一位资深的前端开发工程师和数据可视化专家，精通交互设计和前端动画。

**【任务目标】**
请帮我编写一个“网络数据包收发（Network Packet Flow）”的可视化组件/页面。

**【技术栈】**
请使用包括但不限于 **Next.js + ECharts + Three.js** 来实现，使用design-taste-frontendtas skill 技能作为前端规范

**【核心视觉与动画要求】**

1. **节点展示（Nodes）**：屏幕上会有一个科幻一些的世界地图，地图上需要有两个主要节点类别。
   类别A为服务器端，需要在地图上标注出真实位置；
   类别B为客户端，需要在地图上标注出真实位置。
2. **数据包动画（Animations）**：数据包（用小圆点或小信封图标表示）需要以流畅的动画形式在节点之间移动，模拟发送和接收的过程。
3. **状态颜色（Colors）**：
      - 绿色的包：代表发送/接收成功。
      - 红色的包：代表丢包（到达半路后消失或爆炸特效）。
      - 黄色的包：代表高延迟（移动速度变慢）。
4. **协议区分（Protocols）**：每个数据包需要根据其协议类型（如：TCP、UDP、ICMP）进行分类，并使用不同的颜色来表示。

**【互动要求】**

1. 提供一个“发送数据”的按钮，点击后触发一个新的数据包动画。
2. 鼠标悬停（Hover）在正在移动的数据包上时，可以暂停动画，并弹出一个 Tooltip 显示该包的详细信息（如：源 IP、目的 IP、协议类型、Payload 大小、时间戳）。
3. 提供一个简单的统计面板，实时显示：已发送总数、成功数、丢包率。

**【数据结构参考】**
请基于以下 JSON 结构来驱动你的动画逻辑：

status字段注释：udp状态有"--"、tcp状态可以有"等待"、"请求连接"、\"已连接"、"关闭连接"

向外发包示例：

```json
{
  "id": "pkt_001",
  "timestamp": 1712450000,
  "app_name": "Cloudflare",
  "interface": "wan1",
  "protocol": "tcp",
  "status":"等待连接",
  "source": { "ip": "192.168.1.10","port":35768, "domain": "--", "lat": 39.9042, "lng": 116.4074 },
  "destination": { "ip": "162.159.61.8", "port":443, "domain": "dns.cloudflare.com", "lat": 37.7749, "lng": -122.4194 },
  "total_up": 23588,
  "total_down": 60,
}
```

外部接受数据包示例

```json
{
  "id": "pkt_002",
  "timestamp": 1712450000,
  "app_name": "闲鱼",
  "interface": "lan1",
  "protocol": "tcp",
  "status":"已连接",
  "source": { "ip": "10.0.1.1","port":60866, "domain": "--", "lat": 39.9042, "lng": 116.4074 },
  "destination": { "ip": "203.119.238.180", "port":443, "domain": "h5api.m.goofish.com", "lat": 37.7749, "lng": -122.4194 },
  "total_up": 15562,
  "total_down": 45688,
}
```


内网发包示例【暂时不做展示】

```json
{
  "id": "pkt_003",
  "timestamp": 1712450000,
  "app_name": "未知协议",
  "interface": "lan1",
  "protocol": "udp",
  "status":"--",
  "source": { "ip": "192.168.1.10","port":35768, "domain": "--", "lat": 39.9042, "lng": 116.4074 },
  "destination": { "ip": "162.159.61.8", "port":443, "domain": "--", "lat": 37.7749, "lng": -122.4194 },
  "total_up": 201520,
  "total_down": 157136,
}
```
