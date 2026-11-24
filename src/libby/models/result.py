"""Batch processing result model."""

from dataclasses import dataclass, field


@dataclass
class BatchResult:
    """Result of batch processing."""

    succeeded: list[dict] = field(default_factory=list)
    failed: list[dict] = field(default_factory=list)

    @property
    def total(self) -> int:
        return len(self.succeeded) + len(self.failed)

    @property
    def success_rate(self) -> float:
        if self.total == 0:
            return 0.0
        return len(self.succeeded) / self.total * 100