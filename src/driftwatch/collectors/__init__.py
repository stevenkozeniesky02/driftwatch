"""Infrastructure state collectors."""

from driftwatch.collectors.base import BaseCollector, detect_available_collectors
from driftwatch.collectors.demo import DemoCollector

__all__ = ["BaseCollector", "DemoCollector", "detect_available_collectors"]
