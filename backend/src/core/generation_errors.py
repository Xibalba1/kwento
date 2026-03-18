from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass
class ProviderRequestTimeoutError(RuntimeError):
    provider: str
    model: str
    operation: str
    timeout_seconds: float
    stage: Optional[str] = None

    def __str__(self) -> str:
        return (
            f"{self.provider} request timed out during {self.operation} "
            f"after {self.timeout_seconds}s"
        )


@dataclass
class StoryGenerationTimeoutError(TimeoutError):
    timeout_seconds: float
    stage: str
    provider: Optional[str] = None
    model: Optional[str] = None
    elapsed_seconds: Optional[float] = None

    def __str__(self) -> str:
        return "Story generation timed out"


@dataclass
class BookGenerationTimeoutError(TimeoutError):
    timeout_seconds: float
    stage: str
    provider: Optional[str] = None
    model: Optional[str] = None
    elapsed_seconds: Optional[float] = None

    def __str__(self) -> str:
        return "Book generation timed out"
