"""CoachingPort — abstract interface for all delivery channels.

Every channel adapter (Telegram, CLI, web, app) implements this interface.
The Flow Layer only depends on CoachingPort, never on a concrete channel.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import date
from enum import Enum
from typing import Any


# ---------------------------------------------------------------------------
# Supporting data types
# ---------------------------------------------------------------------------


@dataclass
class Button:
    """A single action button presented to the user."""

    label: str
    callback_data: str


@dataclass
class Option:
    """A selectable option (used in single/multi-select prompts)."""

    label: str
    value: str
    emoji: str | None = None


class InputType(Enum):
    TEXT = "text"
    NUMBER = "number"
    DATE = "date"
    SELECT = "select"
    MULTI_SELECT = "multi_select"
    PHOTO = "photo"


class InputAbortReason(Enum):
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"
    SKIPPED = "skipped"


class InputAborted(Exception):
    def __init__(self, input_type: InputType, reason: InputAbortReason):
        self.input_type = input_type
        self.reason = reason
        super().__init__(f"{input_type.value}:{reason.value}")


@dataclass
class ReportSection:
    """One logical section of a report (text block or image)."""

    content_type: str  # "text" | "image"
    text: str | None = None
    image: bytes | None = None
    caption: str | None = None


@dataclass
class Report:
    """A structured report composed of multiple sections."""

    title: str
    sections: list[ReportSection] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Abstract port
# ---------------------------------------------------------------------------


class CoachingPort(ABC):
    """Abstract interface that every delivery channel must implement.

    The Flow Layer communicates with users exclusively through this port.
    No flow module may import a concrete channel implementation.
    """

    # -- Outbound: sending content to the user --------------------------

    @abstractmethod
    async def send_message(
        self,
        user_id: str,
        text: str,
        buttons: list[Button] | None = None,
    ) -> None:
        """Send a text message, optionally with action buttons."""

    @abstractmethod
    async def send_image(
        self,
        user_id: str,
        image: bytes,
        caption: str | None = None,
    ) -> None:
        """Send an image (chart, report graphic, etc.)."""

    @abstractmethod
    async def send_report(
        self,
        user_id: str,
        report: Report,
    ) -> None:
        """Send a structured multi-section report."""

    # -- Inbound: collecting input from the user ------------------------

    @abstractmethod
    async def request_text(
        self,
        user_id: str,
        prompt: str,
    ) -> str:
        """Ask the user for free-form text input."""

    @abstractmethod
    async def request_number(
        self,
        user_id: str,
        prompt: str,
        min_val: float | None = None,
        max_val: float | None = None,
    ) -> float:
        """Ask the user for a numeric value within optional bounds."""

    @abstractmethod
    async def request_date(
        self,
        user_id: str,
        prompt: str,
    ) -> date:
        """Ask the user for a date."""

    @abstractmethod
    async def request_select(
        self,
        user_id: str,
        prompt: str,
        options: list[Option],
    ) -> str:
        """Present options and return the selected value."""

    @abstractmethod
    async def request_multi_select(
        self,
        user_id: str,
        prompt: str,
        options: list[Option],
    ) -> list[str]:
        """Present options allowing multiple selections; return selected values."""

    @abstractmethod
    async def request_photo(
        self,
        user_id: str,
        prompt: str,
    ) -> bytes | None:
        """Ask the user to send a photo."""
