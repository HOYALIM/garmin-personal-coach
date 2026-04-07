from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timedelta
from typing import Any, Callable

from garmin_coach.adapters.garmin import GarminAdapter
from garmin_coach.engine.readiness import ReadinessCalculator
from garmin_coach.integrations.training_load import build_training_load
from garmin_coach.models import (
    ActivitySummary,
    DailyHealthUpdatedEvent,
    EventDispatchReport,
    HealthMetrics,
    NewActivityEvent,
    SubscriberFailure,
    SyncEventType,
)
from garmin_coach.storage.database import DEFAULT_USER_ID, GarminCoachDatabase
from garmin_coach.training_load_manager import get_training_load_manager


class SyncEventBus:
    def __init__(self) -> None:
        self._handlers: dict[SyncEventType, list[Callable[[Any], None]]] = defaultdict(list)

    def subscribe(self, event_type: SyncEventType, handler: Callable[[Any], None]) -> None:
        self._handlers[event_type].append(handler)

    def emit(self, event_type: SyncEventType, payload: Any) -> EventDispatchReport:
        report = EventDispatchReport(
            event_type=event_type, attempted=len(self._handlers[event_type])
        )
        for handler in self._handlers[event_type]:
            try:
                handler(payload)
                report.delivered += 1
            except Exception as exc:
                report.failures.append(
                    SubscriberFailure(
                        handler_name=getattr(handler, "__name__", handler.__class__.__name__),
                        error_type=type(exc).__name__,
                        message=str(exc),
                    )
                )
        return report

    def on_new_activity(self, handler: Callable[[NewActivityEvent], None]) -> None:
        self.subscribe(SyncEventType.NEW_ACTIVITY, handler)

    def on_daily_health_updated(self, handler: Callable[[DailyHealthUpdatedEvent], None]) -> None:
        self.subscribe(SyncEventType.DAILY_HEALTH_UPDATED, handler)


class GarminSyncService:
    def __init__(
        self,
        adapter: GarminAdapter,
        database: GarminCoachDatabase,
        bus: SyncEventBus | None = None,
        user_id: str = DEFAULT_USER_ID,
    ):
        self.adapter = adapter
        self.database = database
        self.bus = bus or SyncEventBus()
        self.readiness = ReadinessCalculator()
        self.user_id = user_id
        self.last_dispatch_reports: list[EventDispatchReport] = []

    def sync_recent_activities(self, since: datetime | None = None) -> list[ActivitySummary]:
        since = since or (datetime.now() - timedelta(minutes=15))
        items = self.adapter.get_activities(since, datetime.now())
        summaries: list[ActivitySummary] = []
        self.last_dispatch_reports = []
        for item in items:
            details = self.adapter.get_activity_summary(item.activity_id)
            summary = details or ActivitySummary(
                activity_id=item.activity_id,
                type=item.sport_type,
                sport_type=item.sport_type,
                start_time=item.start_time.isoformat(),
                distance_km=(item.distance_meters or 0) / 1000
                if item.distance_meters is not None
                else None,
                duration_min=item.duration_seconds / 60,
                avg_hr=item.heart_rate_avg,
                max_hr=item.heart_rate_max,
                avg_power=item.power_avg,
                calories=item.calories,
                raw=item.raw_data,
            )
            summaries.append(summary)
            activity_key = summary.activity_id or summary.start_time or "unknown"
            activity_date = summary.start_time or datetime.now().isoformat()
            self.database.save_activity(
                self.user_id, activity_key, activity_date, summary.to_dict()
            )
            report = self.bus.emit(
                SyncEventType.NEW_ACTIVITY,
                NewActivityEvent(user_id=self.user_id, activity=summary),
            )
            self.last_dispatch_reports.append(report)
        return summaries

    def sync_daily_health(self, target_date: date | None = None) -> HealthMetrics:
        target_date = target_date or date.today()
        date_str = target_date.isoformat()
        load = build_training_load(get_training_load_manager().calculator, date_str)
        metrics = HealthMetrics(
            metric_date=target_date,
            sleep=self.adapter.get_sleep_data(date_str),
            hrv=self.adapter.get_hrv_data(date_str),
            body_battery=self.adapter.get_body_battery(date_str, date_str),
            stress=self.adapter.get_stress_data(date_str),
            rhr=self.adapter.get_rhr_day(date_str),
            spo2=self.adapter.get_spo2_data(date_str),
            body_composition=self.adapter.get_body_composition(date_str),
            training_readiness=self.adapter.get_training_readiness(date_str),
            training_load=load,
        )
        metrics.readiness = self.readiness.calculate(metrics)
        self.database.save_daily_health(self.user_id, date_str, metrics.to_dict())
        self.database.save_training_load(self.user_id, date_str, metrics.training_load.__dict__)
        self.database.save_readiness(
            self.user_id,
            date_str,
            metrics.readiness.to_dict() if metrics.readiness else {},
        )
        report = self.bus.emit(
            SyncEventType.DAILY_HEALTH_UPDATED,
            DailyHealthUpdatedEvent(user_id=self.user_id, metrics=metrics),
        )
        self.last_dispatch_reports = [report]
        return metrics
