"""PollScheduler：asyncio 轮询调度（doc §5.1.3）。

每个 TaskSpec 独立循环：异常捕获不中断调度，周期带抖动错峰。
"""

import asyncio
import random
from dataclasses import dataclass, field

from core.log import get_logger

log = get_logger("datasource.scheduler")


@dataclass
class TaskSpec:
    name: str
    interval: float
    fn: object  # async callable
    jitter: float = 0.15
    enabled: bool = True


@dataclass
class SchedulerStats:
    runs: dict = field(default_factory=dict)
    errors: dict = field(default_factory=dict)


class PollScheduler:
    def __init__(self) -> None:
        self._specs: list[TaskSpec] = []
        self.stats = SchedulerStats()

    def register(self, spec: TaskSpec) -> None:
        self._specs.append(spec)

    async def _runner(self, spec: TaskSpec, stop: asyncio.Event) -> None:
        # 随机起始相位，避免任务同拍启动
        await asyncio.sleep(random.uniform(0, spec.interval * spec.jitter))
        while not stop.is_set():
            start = asyncio.get_running_loop().time()
            try:
                await spec.fn()
                self.stats.runs[spec.name] = self.stats.runs.get(spec.name, 0) + 1
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                self.stats.errors[spec.name] = self.stats.errors.get(spec.name, 0) + 1
                log.warning("scheduler.task_error", task=spec.name, error=str(exc))
            elapsed = asyncio.get_running_loop().time() - start
            sleep_for = max(0.05, spec.interval - elapsed)
            sleep_for *= 1 + random.uniform(-spec.jitter / 2, spec.jitter / 2)
            try:
                await asyncio.wait_for(stop.wait(), timeout=sleep_for)
            except asyncio.TimeoutError:
                pass

    async def run(self, stop: asyncio.Event) -> None:
        tasks = [
            asyncio.create_task(self._runner(spec, stop), name=spec.name)
            for spec in self._specs
            if spec.enabled
        ]
        log.info("scheduler.started", tasks=[t.get_name() for t in tasks])
        try:
            await stop.wait()
        finally:
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
            log.info("scheduler.stopped")
