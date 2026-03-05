import asyncio
import time
from typing import Optional


class GenerationProgressEstimator:
    """
    Tracks estimated progress for long-running generation workflows and emits
    periodic progress logs with completion %, work remaining, and ETA.
    """

    def __init__(
        self,
        logger,
        enabled: bool = False,
        log_interval_seconds: int = 5,
    ) -> None:
        self.logger = logger
        self.enabled = enabled
        self.log_interval_seconds = max(1, int(log_interval_seconds))

        self._started_at = time.monotonic()
        self._completed_work_units = 0.0
        self._total_work_units = 0.0
        self._stage = "initializing"
        self._ticker_task: Optional[asyncio.Task] = None

    async def start(self) -> None:
        if not self.enabled:
            return
        self._started_at = time.monotonic()
        self._emit_progress_log("Progress tracking started.")
        self._ticker_task = asyncio.create_task(self._periodic_logger())

    async def stop(self, success: bool) -> None:
        if not self.enabled:
            return
        if self._ticker_task:
            self._ticker_task.cancel()
            try:
                await self._ticker_task
            except asyncio.CancelledError:
                pass
        self._stage = "completed" if success else "failed"
        self._emit_progress_log("Progress tracking finished.")

    def set_stage(self, stage: str) -> None:
        if not self.enabled:
            return
        self._stage = stage

    def add_total_work(self, units: float) -> None:
        if not self.enabled:
            return
        self._total_work_units = max(
            self._completed_work_units, self._total_work_units + max(0.0, units)
        )

    def mark_work_completed(self, units: float = 1.0, note: Optional[str] = None) -> None:
        if not self.enabled:
            return
        self._completed_work_units = min(
            self._total_work_units,
            self._completed_work_units + max(0.0, units),
        )
        self._emit_progress_log("Progress updated.", note=note)

    def _progress_snapshot(self) -> dict:
        elapsed_seconds = max(0.0, time.monotonic() - self._started_at)
        remaining_units = max(0.0, self._total_work_units - self._completed_work_units)
        completion_pct = (
            (self._completed_work_units / self._total_work_units) * 100.0
            if self._total_work_units > 0
            else 0.0
        )

        eta_seconds = None
        if self._completed_work_units > 0 and elapsed_seconds > 0:
            work_rate = self._completed_work_units / elapsed_seconds
            if work_rate > 0:
                eta_seconds = remaining_units / work_rate

        return {
            "stage": self._stage,
            "completed_work_units": round(self._completed_work_units, 2),
            "total_work_units": round(self._total_work_units, 2),
            "remaining_work_units": round(remaining_units, 2),
            "completion_pct": round(completion_pct, 2),
            "elapsed_seconds": round(elapsed_seconds, 1),
            "eta_seconds": round(eta_seconds, 1) if eta_seconds is not None else None,
        }

    def _emit_progress_log(self, message: str, note: Optional[str] = None) -> None:
        snapshot = self._progress_snapshot()
        if note:
            snapshot["note"] = note
        self.logger.info(f"{message} | generation_progress={snapshot}")

    async def _periodic_logger(self) -> None:
        while True:
            await asyncio.sleep(self.log_interval_seconds)
            self._emit_progress_log("Periodic progress estimate.")
