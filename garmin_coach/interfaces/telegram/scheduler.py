"""Telegram scheduler — automated message delivery.

Manages scheduled jobs for:
- Morning briefing (user-configured time, default 07:00)
- Evening check-in (user-configured time, default 21:00)
- Weekly report (Sunday 20:00)
- Monthly report (1st of month, 09:00)
- Post-workout analysis (event-driven, not scheduled)
"""

from __future__ import annotations

import logging
from datetime import time as dt_time
from typing import Any, Protocol

from garmin_coach.interfaces.telegram import renderer

logger = logging.getLogger(__name__)

# Default schedule times
DEFAULT_MORNING_TIME = dt_time(7, 0)
DEFAULT_EVENING_TIME = dt_time(21, 0)
DEFAULT_WEEKLY_TIME = dt_time(20, 0)  # Sunday
DEFAULT_MONTHLY_TIME = dt_time(9, 0)  # 1st of month


class UserConfigProvider(Protocol):
    """Provides per-user schedule configuration."""

    async def get_schedule_config(self, user_id: str) -> dict[str, Any]: ...
    async def get_all_user_ids(self) -> list[str]: ...


class ReportGenerator(Protocol):
    async def generate_weekly(self, user_id: str) -> dict[str, Any]: ...
    async def generate_monthly(self, user_id: str) -> dict[str, Any]: ...


class MessageDeliveryPort(Protocol):
    async def send_message(self, user_id: str, text: str) -> None: ...


class TelegramScheduler:
    """Manages scheduled coaching jobs via python-telegram-bot JobQueue.

    Designed to work with python-telegram-bot v20+ Application.job_queue.
    """

    def __init__(
        self,
        flows: Any,  # FlowRegistry
        user_config: UserConfigProvider | None = None,
        delivery: MessageDeliveryPort | None = None,
        reports: ReportGenerator | None = None,
    ) -> None:
        self.flows = flows
        self.user_config = user_config
        self.delivery = delivery
        self.reports = reports
        self._job_queue: Any = None

    def setup(self, job_queue: Any) -> None:
        """Attach to a python-telegram-bot JobQueue and schedule default jobs.

        Call this after Application is built.
        """
        self._job_queue = job_queue

        # Schedule daily jobs at default times
        # These will be refined per-user when user configs are loaded
        job_queue.run_daily(
            self._morning_briefing_job,
            time=DEFAULT_MORNING_TIME,
            name="morning_briefing",
        )
        job_queue.run_daily(
            self._evening_checkin_job,
            time=DEFAULT_EVENING_TIME,
            name="evening_checkin",
        )
        # Weekly report: Sunday at 20:00
        job_queue.run_daily(
            self._weekly_report_job,
            time=DEFAULT_WEEKLY_TIME,
            days=(6,),  # Sunday = 6
            name="weekly_report",
        )
        # Monthly report: 1st of month at 09:00
        job_queue.run_monthly(
            self._monthly_report_job,
            when=DEFAULT_MONTHLY_TIME,
            day=1,
            name="monthly_report",
        )

        logger.info("TelegramScheduler: default jobs scheduled")

    async def schedule_for_user(self, user_id: str) -> None:
        """Set up per-user scheduled jobs based on their preferences."""
        if not self.user_config or not self._job_queue:
            return

        try:
            config = await self.user_config.get_schedule_config(user_id)
        except Exception:
            logger.debug("No schedule config for user %s, using defaults", user_id)
            return

        morning_time = _parse_time(config.get("morning_time"), DEFAULT_MORNING_TIME)
        evening_time = _parse_time(config.get("evening_time"), DEFAULT_EVENING_TIME)

        # Remove existing per-user jobs
        self._remove_user_jobs(user_id)

        # Schedule per-user morning briefing
        self._job_queue.run_daily(
            self._morning_briefing_job,
            time=morning_time,
            name=f"morning_{user_id}",
            data={"user_id": user_id},
        )

        # Schedule per-user evening check-in
        self._job_queue.run_daily(
            self._evening_checkin_job,
            time=evening_time,
            name=f"evening_{user_id}",
            data={"user_id": user_id},
        )

        logger.info(
            "Scheduled for user %s: morning=%s, evening=%s",
            user_id,
            morning_time,
            evening_time,
        )

    def _remove_user_jobs(self, user_id: str) -> None:
        """Remove existing scheduled jobs for a user."""
        if not self._job_queue:
            return
        for name in [f"morning_{user_id}", f"evening_{user_id}"]:
            jobs = self._job_queue.get_jobs_by_name(name)
            for job in jobs:
                job.schedule_removal()

    # -- Job callbacks --------------------------------------------------

    async def _morning_briefing_job(self, context: Any) -> None:
        """Execute morning briefing for all users or a specific user."""
        user_ids = await self._get_target_users(context)
        for user_id in user_ids:
            try:
                if self.flows and self.flows.morning_briefing:
                    await self.flows.morning_briefing.execute(user_id)
            except Exception:
                logger.exception("Morning briefing failed for user %s", user_id)

    async def _evening_checkin_job(self, context: Any) -> None:
        """Execute evening check-in for all users or a specific user."""
        user_ids = await self._get_target_users(context)
        for user_id in user_ids:
            try:
                if self.flows and self.flows.evening_checkin:
                    await self.flows.evening_checkin.execute(user_id)
            except Exception:
                logger.exception("Evening check-in failed for user %s", user_id)

    async def _weekly_report_job(self, context: Any) -> None:
        """Execute weekly report for all users."""
        user_ids = await self._get_all_users()
        for user_id in user_ids:
            try:
                await self._deliver_report(user_id, period="weekly")
            except Exception:
                logger.exception("Weekly report failed for user %s", user_id)

    async def _monthly_report_job(self, context: Any) -> None:
        """Execute monthly report for all users."""
        user_ids = await self._get_all_users()
        for user_id in user_ids:
            try:
                await self._deliver_report(user_id, period="monthly")
            except Exception:
                logger.exception("Monthly report failed for user %s", user_id)

    # -- Event-driven triggers ------------------------------------------

    async def on_new_activity(
        self, activity: dict[str, Any] | Any, user_id: str | None = None
    ) -> None:
        """Called when S1 sync detects a new activity — triggers post-workout flow."""
        activity_payload = self._normalize_activity(activity)
        target_users = [user_id] if user_id else await self._get_all_users()
        for target_user in [uid for uid in target_users if uid]:
            try:
                if self.flows and self.flows.post_workout:
                    await self.flows.post_workout.execute(target_user, activity_payload)
            except Exception:
                logger.exception("Post-workout flow failed for user %s", target_user)

    # -- Helpers --------------------------------------------------------

    async def _get_target_users(self, context: Any) -> list[str]:
        """Get target user IDs from job data or all users."""
        if context.job and context.job.data and "user_id" in context.job.data:
            return [context.job.data["user_id"]]
        return await self._get_all_users()

    async def _get_all_users(self) -> list[str]:
        if self.user_config:
            try:
                return await self.user_config.get_all_user_ids()
            except Exception:
                logger.exception("Failed to get user list")
        return []

    async def _deliver_report(self, user_id: str, period: str) -> None:
        if not self.reports or not self.delivery:
            logger.warning(
                "%s report skipped for user %s: runtime dependencies missing", period, user_id
            )
            return

        report_data = (
            await self.reports.generate_weekly(user_id)
            if period == "weekly"
            else await self.reports.generate_monthly(user_id)
        )
        for message in renderer.render_weekly_report(report_data):
            await self.delivery.send_message(user_id, message)

    def _normalize_activity(self, activity: dict[str, Any] | Any) -> dict[str, Any]:
        if isinstance(activity, dict):
            return activity
        if hasattr(activity, "to_dict"):
            result = activity.to_dict()
            if isinstance(result, dict):
                return result
        if hasattr(activity, "__dict__"):
            return {key: value for key, value in vars(activity).items() if not key.startswith("_")}
        return {}


def _parse_time(value: Any, default: dt_time) -> dt_time:
    """Parse a time string (HH:MM) or return default."""
    if isinstance(value, dt_time):
        return value
    if isinstance(value, str):
        try:
            parts = value.split(":")
            return dt_time(int(parts[0]), int(parts[1]))
        except (ValueError, IndexError):
            pass
    return default
