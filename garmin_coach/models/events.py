from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from .health_metrics import ActivitySummary, HealthMetrics


class SyncEventType(str, Enum):
    NEW_ACTIVITY = "on_new_activity"
    DAILY_HEALTH_UPDATED = "on_daily_health_updated"


@dataclass
class NewActivityEvent:
    user_id: str
    activity: ActivitySummary
    emitted_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return {
            "user_id": self.user_id,
            "activity": self.activity.to_dict(),
            "emitted_at": self.emitted_at,
        }


@dataclass
class DailyHealthUpdatedEvent:
    user_id: str
    metrics: HealthMetrics
    emitted_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return {
            "user_id": self.user_id,
            "metrics": self.metrics.to_dict(),
            "emitted_at": self.emitted_at,
        }


@dataclass
class SubscriberFailure:
    handler_name: str
    error_type: str
    message: str


@dataclass
class EventDispatchReport:
    event_type: SyncEventType
    attempted: int = 0
    delivered: int = 0
    failures: list[SubscriberFailure] = field(default_factory=list)

    @property
    def failed(self) -> int:
        return len(self.failures)
