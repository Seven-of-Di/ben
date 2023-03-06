import psutil
import threading
from typing import List


class HealthChecker:
    cpu_usage: List[float]

    def __init__(self, logger) -> None:
        self.cpu_usage = []
        self.logger = logger

    def healthy(self) -> bool:
        for cpu_per_core in self.cpu_usage:
            if cpu_per_core > 95:
                return False

        return True

    def start(self):
        self.logger.warning("Started HealthChecker")

        x = threading.Thread(target=self.start_metrics_loop)
        x.start()

    def start_metrics_loop(self):
        while True:
            self.cpu_usage = psutil.cpu_percent(interval=15, percpu=True)
            self.logger.warning(self.cpu_usage)
