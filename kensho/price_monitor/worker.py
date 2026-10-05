"""Background worker daemon for periodic price monitoring checks."""

from __future__ import annotations

import logging
import time
from .service import PriceMonitorService

logger = logging.getLogger(__name__)


class PriceMonitorWorker:
    """Worker daemon executing due price checks."""

    def __init__(self, service: PriceMonitorService | None = None, loop_interval_sec: int = 60):
        self.service = service or PriceMonitorService()
        self.loop_interval_sec = loop_interval_sec
        self.running = False

    def run_once(self) -> list[dict]:
        """Execute a single batch of due price checks."""
        logger.info("Executing price check cycle...")
        results = self.service.run_due_checks()
        logger.info(f"Price check cycle completed: {len(results)} rules processed.")
        return results

    def start_loop(self) -> None:
        """Start infinite worker loop."""
        self.running = True
        logger.info(f"Starting PriceMonitorWorker loop (interval: {self.loop_interval_sec}s)")
        try:
            while self.running:
                self.run_once()
                time.sleep(self.loop_interval_sec)
        except KeyboardInterrupt:
            logger.info("Worker stopped by KeyboardInterrupt.")
        finally:
            self.running = False

    def stop(self) -> None:
        self.running = False
