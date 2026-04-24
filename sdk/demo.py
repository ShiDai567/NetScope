#!/usr/bin/env python3

import json
import sys
from pathlib import Path


# 确保直接执行 `python sdk/demo.py` 时，
# 可以导入当前目录下的 `ikuai_sdk` 包，而不需要先安装成全局包。
SDK_DIR = Path(__file__).resolve().parent
if str(SDK_DIR) not in sys.path:
    sys.path.insert(0, str(SDK_DIR))

from ikuai_sdk import IKuaiClient, IKuaiNetworkError, IKuaiValidationError


# Demo 相关文件：
# - `.env` 用来保存爱快地址、用户名、密码
# - `demo_result.json` 用来保存最终结果，方便后续查看
ENV_FILE = SDK_DIR / ".env"
OUTPUT_FILE = SDK_DIR / "demo_result.json"


def load_env_file(path: Path) -> dict[str, str]:
    # 读取最简单的 KEY=VALUE 格式配置文件。
    # 这里故意不用第三方 dotenv 依赖，让 demo 保持独立、开箱即用。
    values: dict[str, str] = {}
    if not path.exists():
        return values

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def main() -> int:
    # 从 `sdk/.env` 中读取配置。
    # 这里保留默认值，只是为了让字段结构更直观；实际使用时建议都在 `.env` 中填写。
    config = load_env_file(ENV_FILE)
    router_url = config.get("IKUAI_ROUTER_URL", "http://10.1.1.1")
    username = config.get("IKUAI_USERNAME", "admin")
    password = config.get("IKUAI_PASSWORD", "123")

    # 创建 SDK 客户端。
    # 这里使用默认超时即可满足 demo 场景。
    client = IKuaiClient()

    try:
        # 第一步：
        # 登录爱快，并立即获取终端列表。
        #
        # `login_result` 里会包含登录结果、sess_key、cookie_header。
        # `terminal_result` 里会包含 `/Action/call` 返回的终端列表数据。
        login_result, terminal_result = client.login_and_get_terminal_list(
            router_url=router_url,
            username=username,
            password=password,
        )
    except IKuaiValidationError as exc:
        print(f"配置错误：{exc}")
        print("请先填写 sdk/.env。")
        return 1
    except IKuaiNetworkError as exc:
        print(f"网络错误：{exc}")
        return 2

    # 第二步：
    # 从终端列表响应中提取设备列表。
    #
    # 爱快通常会把真实数据放在 `Data.data` 下，
    # 这里做了兜底处理，避免字段不存在时报错。
    terminals = (terminal_result.data or {}).get("data") or []
    terminal_connections = []
    for device in terminals:
        # 不同固件版本里，设备 IP 字段名可能略有不同，
        # 所以这里优先取 `ip_addr`，取不到再尝试 `ip`。
        device_ip = device.get("ip_addr") or device.get("ip")
        if not device_ip:
            continue

        # 第三步：
        # 针对每个设备 IP，继续请求它的连接详询。
        # 这里底层实际使用的是：
        # TYPE = "conn,conn_num"
        #
        # `/Action/call` 的请求体已经由 SDK 内部封装好了，
        # demo 这里只需要传设备 IP 即可。
        connection_result = client.get_terminal_connection_details(
            router_url=router_url,
            cookie_header=login_result.cookie_header,
            ip=device_ip,
        )

        # 最终结果里只保留常用字段：
        # 设备基础信息 + 连接数 + 连接列表。
        terminal_connections.append(
            {
                "ip": device_ip,
                "comment": device.get("comment"),
                "mac": device.get("mac"),
                "conn_num": (connection_result.data or {}).get("conn_num"),
                "conn": (connection_result.data or {}).get("conn"),
            }
        )

    # 第四步：
    # 组装最终结果，统一写入一个 JSON 文件中。
    # 这里包含三部分：
    # - 登录结果摘要
    # - 终端列表摘要
    # - 每个终端对应的连接详询
    output = {
        "login": {
            "result_code": login_result.result_code,
            "result_message": login_result.result_message,
            "sess_key": login_result.sess_key,
            "cookie_header": login_result.cookie_header,
            "request_mode": login_result.request_mode,
            "upstream_status": login_result.upstream_status,
        },
        "terminal_list": {
            "result_code": terminal_result.result_code,
            "result_message": terminal_result.result_message,
            "total": (terminal_result.data or {}).get("total"),
            "data": (terminal_result.data or {}).get("data"),
        },
        "terminal_connections": terminal_connections,
    }

    # 第五步：
    # 不直接打印结果，而是保存到 `sdk/demo_result.json`。
    # 这样更方便后续查看，也便于别的脚本继续读取这个结果文件。
    OUTPUT_FILE.write_text(
        json.dumps(output, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    # 把 main() 的返回值作为脚本退出码返回给 shell。
    raise SystemExit(main())
