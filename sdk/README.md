# iKuai SDK

这是一个用于调用爱快面板登录接口的 Python SDK。

当前 SDK 的目标很聚焦：

- 按爱快面板接口要求生成登录参数
- 自动将明文密码转成 32 位小写 MD5
- 优先用 JSON 方式登录，失败后自动回退为表单方式
- 支持调用 `/Action/call`
- 内置“获取终端列表”和“单设备连接详询”能力
- 从响应中提取 `sess_key`
- 生成后续接口可直接复用的 `Cookie` 头
- 返回统一的数据结构，方便集成到 Django、Flask、脚本或其他服务中

## 目录结构

```text
sdk/
├── README.md
├── demo.py
└── ikuai_sdk/
    ├── __init__.py
    ├── client.py
    ├── exceptions.py
    └── models.py
```

## 爱快登录接口说明

SDK 当前封装的是爱快面板登录接口：

- 地址：`{router_url}/Action/login`
- 方法：`POST`

请求字段：

- `username`: 用户名
- `passwd`: 密码的 MD5，32 位小写
- `pass`: 随机字符串，长度 20
- `remember_password`: 记住密码字段，可为空字符串

成功响应示例：

```json
{
  "Result": 10000,
  "ErrMsg": "Succeess"
}
```

失败响应示例：

```json
{
  "Result": 10001,
  "ErrMsg": "用户名或密码错误"
}
```

成功时通常会返回类似这样的 Cookie：

```text
sess_key=0249f5edebd84e26103c1193a4ede2c8
```

后续请求通常可使用：

```text
sess_key=<sess_key>; username=<username>; login=1
```

SDK 已自动帮你拼好这个 `cookie_header`。

## 运行要求

- Python 3.10+
- 仅使用 Python 标准库，不依赖第三方包

## 快速开始

### 1. 在代码里直接调用

```python
from ikuai_sdk import IKuaiClient


client = IKuaiClient(timeout=10)
result = client.login(
    router_url="http://10.1.1.1",
    username="admin",
    password="123",
)

print(result.result_code)
print(result.result_message)
print(result.sess_key)
print(result.cookie_header)
```

### 2. 返回对象说明

`login()` 返回 [`IKuaiLoginResult`](./ikuai_sdk/models.py) 对象，包含这些主要字段：

- `router_url`: 路由器基础地址
- `login_url`: 实际登录地址
- `username`: 登录用户名
- `request_mode`: 本次使用的请求模式，`json` 或 `form`
- `request_payload`: 实际发送给爱快的 payload
- `upstream_status`: 爱快返回的 HTTP 状态码
- `upstream_response`: 爱快返回的 JSON 或原始内容
- `response_headers`: 爱快返回的响应头
- `cookies`: 解析后的 cookies 字典
- `sess_key`: 提取到的 `sess_key`
- `cookie_header`: 拼接好的后续请求 Cookie 头

还有两个便捷属性：

- `result_code`: 从响应里取出的 `Result`
- `result_message`: 从响应里取出的 `ErrMsg`

`call()`、`get_terminal_list()` 和 `get_terminal_connection_details()` 返回 `IKuaiCallResult`，主要字段有：

- `path`: 请求路径，例如 `/Action/call`
- `payload`: 实际发送的请求体
- `upstream_status`: HTTP 状态码
- `upstream_response`: 爱快返回的 JSON
- `response_headers`: 响应头
- `data`: 便捷属性，对应 `upstream_response["Data"]`
- `result_code`: 便捷属性，对应 `upstream_response["Result"]`
- `result_message`: 便捷属性，对应 `upstream_response["ErrMsg"]`

### 3. 登录成功判断

```python
if result.result_code == 10000:
    print("登录成功")
elif result.result_code == 10001:
    print("用户名或密码错误")
else:
    print("返回了非预期结果")
```

## 异常说明

SDK 暴露了这几个异常：

- `IKuaiError`: 基础异常
- `IKuaiValidationError`: 参数校验失败
- `IKuaiNetworkError`: 网络错误、连接失败、超时等

示例：

```python
from ikuai_sdk import IKuaiClient, IKuaiNetworkError, IKuaiValidationError


client = IKuaiClient()

try:
    result = client.login(
        router_url="http://10.1.1.1",
        username="admin",
        password="123",
    )
except IKuaiValidationError as exc:
    print(f"参数错误: {exc}")
except IKuaiNetworkError as exc:
    print(f"网络错误: {exc}")
else:
    print(result.upstream_response)
```

## SDK API

### `IKuaiClient`

位置：[sdk/ikuai_sdk/client.py](/workspace/gitlab/NetScope/sdk/ikuai_sdk/client.py:1)

#### 初始化

```python
client = IKuaiClient(timeout=10)
```

参数：

- `timeout`: HTTP 请求超时秒数，默认 `10`

#### `login()`

```python
result = client.login(
    router_url="http://10.1.1.1",
    username="admin",
    password="123",
    remember_password="",
)
```

参数：

- `router_url`: 爱快面板基础地址，例如 `http://10.1.1.1`
- `username`: 用户名
- `password`: 明文密码，SDK 内部会转换成 MD5
- `remember_password`: 可选，默认 `""`

行为：

1. 标准化 `router_url`
2. 校验必填参数
3. 把 `password` 转成 32 位小写 MD5
4. 生成 20 位随机 `pass`
5. 先发 JSON 请求
6. 如果没有拿到明确的爱快登录结果，则退回表单请求
7. 解析响应、cookies 和 `sess_key`
8. 返回统一结果对象

#### `call()`

用于发送通用 `/Action/call` 请求：

```python
call_result = client.call(
    router_url="http://10.1.1.1",
    cookie_header=login_result.cookie_header,
    payload={
        "func_name": "dns",
        "action": "show",
        "param": {
            "TYPE": "total,data",
            "limit": "0,20",
            "ORDER_BY": "",
            "ORDER": "",
        },
    },
)
```

#### `get_terminal_list()`

获取在线终端列表：

```python
terminal_result = client.get_terminal_list(
    router_url="http://10.1.1.1",
    cookie_header=login_result.cookie_header,
)

print(terminal_result.data.get("total"))
print(terminal_result.data.get("data"))
```

SDK 内部默认发送：

```json
{
  "func_name": "monitor_lanip",
  "action": "show",
  "param": {
    "TYPE": "data,total",
    "ORDER_BY": "ip_addr_int",
    "orderType": "IP",
    "limit": "0,100",
    "ORDER": ""
  }
}
```

#### `get_terminal_connection_details()`

获取某个设备的连接详询，请求体就是你给的这类格式：

```python
connection_result = client.get_terminal_connection_details(
    router_url="http://10.1.1.1",
    cookie_header=login_result.cookie_header,
    ip="10.0.1.2",
)

print(connection_result.data.get("conn_num"))
print(connection_result.data.get("conn"))
```

SDK 内部默认发送：

```json
{
  "func_name": "monitor_lanip",
  "action": "show",
  "param": {
    "TYPE": "conn,conn_num",
    "ip": "10.0.1.2",
    "interface": "all",
    "proto": "all",
    "maxnum": 500,
    "limit": "0,100",
    "ORDER_BY": "",
    "ORDER": ""
  }
}
```

#### `login_and_get_terminal_list()`

如果你想一步完成“登录 + 获取终端列表”，可以直接用：

```python
login_result, terminal_result = client.login_and_get_terminal_list(
    router_url="http://10.1.1.1",
    username="admin",
    password="123",
)
```

#### `login_and_get_terminal_connection_details()`

如果你已经知道某个终端 IP，也可以一步完成“登录 + 拉连接详询”：

```python
login_result, connection_result = client.login_and_get_terminal_connection_details(
    router_url="http://10.1.1.1",
    username="admin",
    password="123",
    ip="10.0.1.2",
)
```

## 使用 Demo

本目录提供了一个可直接运行的使用示例：

- [sdk/demo.py](/workspace/gitlab/NetScope/sdk/demo.py:1)

### 直接运行

先在 `sdk/` 目录下创建 `.env`，可以直接参考 [sdk/.env.example](/workspace/gitlab/NetScope/sdk/.env.example:1)：

```env
IKUAI_ROUTER_URL=http://10.1.1.1
IKUAI_USERNAME=admin
IKUAI_PASSWORD=123
```

然后直接运行：

```bash
python sdk/demo.py
```

运行结果会保存到：

```text
sdk/demo_result.json
```

这个 demo 会演示：

- 如何创建 `IKuaiClient`
- 如何调用 `login()`
- 如何调用终端列表接口
- 如何拿某个设备的连接详询
- 如何拿到 `sess_key`
- 如何读取终端列表数据

## Demo 跑通后的下一步

如果 demo 跑通，你就已经拿到了：

- 登录返回的 `sess_key`
- 后续调用可复用的 `cookie_header`
- `/Action/call` 返回的终端列表
- 每个终端 IP 对应的连接详询

示例：

```python
cookie_header = result.cookie_header
print(cookie_header)
```

结果通常像这样：

```text
sess_key=0249f5edebd84e26103c1193a4ede2c8; username=admin; login=1
```

## 常见问题

### 1. `routerUrl, username, password are required`

说明调用时缺了必填字段。

### 2. 返回 `10001`

说明用户名或密码错误。

### 3. 连不上路由器

通常是以下原因：

- 路由器地址不对
- 本机到爱快网络不通
- 端口被代理或防火墙拦住
- 面板不是 HTTP，而你填成了 HTTPS，或相反

### 4. 登录成功但没有 `sess_key`

这说明爱快返回格式和当前设备版本存在差异，需要抓包确认响应头里的 `Set-Cookie` 实际内容。

## 当前限制

- 目前只内置了登录、终端列表、单设备连接详询这几个高频能力
- `/Action/call` 其他功能仍需你自己传 `func_name` / `action` / `param`
- 还没有发布成独立 pip 包

## 后续建议

下一步很适合继续补这几个能力：

- 通用 `post(path, data)` 能力
- 自动续期或重新登录
- `pyproject.toml` 打包配置
