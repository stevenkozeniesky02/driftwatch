"""Base collector interface and discovery."""

from __future__ import annotations

import shutil
import subprocess
from abc import ABC, abstractmethod

from driftwatch.models import CollectorType, Resource


class BaseCollector(ABC):
    """Abstract base for infrastructure state collectors."""

    @property
    @abstractmethod
    def collector_type(self) -> CollectorType:
        ...

    @abstractmethod
    def is_available(self) -> bool:
        """Check if this collector's prerequisites are met."""
        ...

    @abstractmethod
    def collect(self) -> list[Resource]:
        """Collect current infrastructure state."""
        ...

    def _run_command(self, cmd: list[str], timeout: int = 30) -> str | None:
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False,
            )
            if result.returncode == 0:
                return result.stdout
            return None
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return None


def _has_command(name: str) -> bool:
    return shutil.which(name) is not None


def detect_available_collectors() -> list[CollectorType]:
    available = []
    if _has_command("aws"):
        available.append(CollectorType.AWS)
    if _has_command("terraform"):
        available.append(CollectorType.TERRAFORM)
    if _has_command("docker"):
        available.append(CollectorType.DOCKER)
    if _has_command("kubectl"):
        available.append(CollectorType.KUBERNETES)
    return available
