import psutil
import threading
from typing import List
import logging

class HealthChecker:
    cpu_usage: List[float]

    def __init__(self) -> None:
        self.cpu_usage = []

    def healthy(self) -> bool:
        for cpu_per_core in self.cpu_usage:
            if cpu_per_core > 95:
                logging.warning(self.cpu_usage)
                return False

        return True

    def start(self):
        x = threading.Thread(target=self.start_metrics_loop)
        x.start()

    def start_metrics_loop(self):
        while True:
            self.cpu_usage = psutil.cpu_percent(interval=15, percpu=True)
