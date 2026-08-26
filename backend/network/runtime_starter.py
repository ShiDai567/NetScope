"""进程内 collector 启动器（RUN_COLLECTOR_IN_PROCESS=1，仅开发）。

runserver 自动重载会父子双进程，用 RUN_MAIN 环境变量保证只启动一次；
daphne/uvicorn 直启场景（无 RUN_MAIN）也允许拉起。
"""

import asyncio
import os
import threading

from django.conf import settings

_STARTED = False


def maybe_start_in_process_collector() -> None:
    global _STARTED
    if _STARTED:
        return
    if not getattr(settings, "RUN_COLLECTOR_IN_PROCESS", False):
        return
    if not getattr(settings, "DEBUG", False):
        return
    if "pytest" in os.sys.argv[0] or os.environ.get("PYTEST_CURRENT_TEST"):
        return  # 测试进程禁用
    if os.environ.get("DJANGO_RUN_COLLECTOR") == "0":
        return
    in_runserver = "runserver" in os.environ.get("DJANGO_RUNSERVER", "") or any(
        "runserver" in arg for arg in os.sys.argv[1:]
    )
    if in_runserver and os.environ.get("RUN_MAIN") != "true":
        return  # autoreload 父进程不启动
    _STARTED = True

    def _boot() -> None:
        asyncio.run(_run())

    thread = threading.Thread(target=_boot, name="collector", daemon=True)
    thread.start()


async def _run() -> None:
    from network.collector import CollectorRuntime, build_source

    runtime = CollectorRuntime(build_source(settings), settings)
    await runtime.run()
