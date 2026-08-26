"""collect_network：collector 独立进程入口（生产部署方式）。"""

import asyncio
import signal

from django.conf import settings
from django.core.management.base import BaseCommand

from core.log import configure_logging, get_logger

log = get_logger("network.commands.collect")


class Command(BaseCommand):
    help = "启动网络采集器（iKuai/mock → Redis → WebSocket 广播）"

    def add_arguments(self, parser) -> None:
        parser.add_argument("--mock", action="store_true", help="强制使用 mock 数据源")
        parser.add_argument("--once", action="store_true", help="单轮采集后退出（调试用）")

    def handle(self, *args, **options) -> None:
        if options.get("mock") and settings.DATA_SOURCE != "mock":
            settings.DATA_SOURCE = "mock"

        from network.collector import CollectorRuntime, build_source

        source = build_source(settings)
        runtime = CollectorRuntime(source, settings)

        if options.get("once"):
            asyncio.run(self._run_once(runtime))
            return

        stop = asyncio.Event()
        loop = asyncio.new_event_loop()

        def _signal(*_args) -> None:
            stop.set()

        for sig in (signal.SIGINT, signal.SIGTERM):
            try:
                loop.add_signal_handler(sig, _signal)
            except NotImplementedError:
                signal.signal(sig, _signal)

        try:
            loop.run_until_complete(self._run_with_stop(runtime, stop))
        except KeyboardInterrupt:
            pass
        finally:
            loop.close()

    async def _run_with_stop(self, runtime, stop) -> None:
        configure_logging(getattr(settings, "LOG_LEVEL", "INFO"))
        self.stdout.write(self.style.SUCCESS("collector 启动"))

        # 复用 runtime 已注册的任务，把停止信号注入调度器
        await self._run_scheduler_with_stop(runtime, stop)

    async def _run_scheduler_with_stop(self, runtime, stop) -> None:
        scheduler = runtime._scheduler  # noqa: SLF001
        # PollScheduler.run 只接受 Event；重建一个绑定 stop 的运行
        import asyncio as _asyncio

        tasks = []
        from datasource.ikuai.scheduler import TaskSpec  # noqa: F401

        specs = list(scheduler._specs)  # noqa: SLF001
        runner = scheduler._runner  # noqa: SLF001
        tasks = [_asyncio.create_task(runner(spec, stop), name=spec.name) for spec in specs]
        try:
            await stop.wait()
        finally:
            for task in tasks:
                task.cancel()
            await _asyncio.gather(*tasks, return_exceptions=True)

    async def _run_once(self, runtime) -> None:
        """单轮：terminals → connections → iface → 立即聚合一次。"""

        await runtime._task_terminals()
        await runtime._task_connections()
        await runtime._task_iface()
        await runtime._task_aggregate()
        store = runtime.store
        mode = store.get_mode()
        totals = store.get_totals()
        self.stdout.write(
            self.style.SUCCESS(
                f"mode={mode.get('mode')} total={totals.get('total', 0)} "
                f"active={runtime.conns.active_count()} seq={store.last_seq()}"
            )
        )
