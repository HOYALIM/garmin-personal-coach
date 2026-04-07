"""Reusable Telegram inline keyboard components.

Design principles:
- Max 3 buttons per row
- Current selection shown with ✅ prefix
- All keyboards include a cancel option where appropriate
"""

from __future__ import annotations

import importlib
from typing import Any


def _load_telegram():
    telegram = importlib.import_module("telegram")
    return telegram


def single_select(options: list[tuple[str, str]], cols: int = 2) -> Any:
    """Build a single-select inline keyboard.

    Args:
        options: List of (label, callback_data) tuples.
        cols: Number of buttons per row (max 3).
    """
    telegram = _load_telegram()
    cols = min(cols, 3)

    rows: list[list[Any]] = []
    row: list[Any] = []
    for label, data in options:
        row.append(telegram.InlineKeyboardButton(text=label, callback_data=data))
        if len(row) >= cols:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    return telegram.InlineKeyboardMarkup(rows)


def multi_select(
    options: list[tuple[str, str]],
    selected: set[str],
    cols: int = 2,
) -> Any:
    """Build a multi-select toggle keyboard with a 'done' button.

    Args:
        options: List of (label, value) tuples.
        selected: Currently selected values.
        cols: Number of buttons per row.
    """
    telegram = _load_telegram()
    cols = min(cols, 3)

    rows: list[list[Any]] = []
    row: list[Any] = []
    for label, value in options:
        prefix = "✅ " if value in selected else ""
        row.append(
            telegram.InlineKeyboardButton(
                text=f"{prefix}{label}", callback_data=f"msel:{value}"
            )
        )
        if len(row) >= cols:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append([telegram.InlineKeyboardButton(text="✅ 완료", callback_data="msel:__done__")])
    return telegram.InlineKeyboardMarkup(rows)


def number_scale(
    min_val: int = 1,
    max_val: int = 10,
    prefix: str = "rpe",
    cols: int = 5,
) -> Any:
    """Build a numeric scale keyboard (e.g., RPE 1-10).

    Args:
        min_val: Minimum value.
        max_val: Maximum value.
        prefix: Callback data prefix.
        cols: Buttons per row.
    """
    telegram = _load_telegram()
    cols = min(cols, 5)

    rows: list[list[Any]] = []
    row: list[Any] = []
    for i in range(min_val, max_val + 1):
        row.append(
            telegram.InlineKeyboardButton(text=str(i), callback_data=f"{prefix}:{i}")
        )
        if len(row) >= cols:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    return telegram.InlineKeyboardMarkup(rows)


def emoji_select(options: list[tuple[str, str, str]]) -> Any:
    """Build an emoji-based selection keyboard.

    Args:
        options: List of (emoji, label, callback_data) tuples.
    """
    telegram = _load_telegram()
    rows: list[list[Any]] = []
    row: list[Any] = []
    for emoji, label, data in options:
        row.append(
            telegram.InlineKeyboardButton(text=f"{emoji} {label}", callback_data=data)
        )
        if len(row) >= 3:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    return telegram.InlineKeyboardMarkup(rows)


def confirm_cancel(
    confirm_text: str = "✅ 확인",
    cancel_text: str = "❌ 취소",
    confirm_data: str = "confirm",
    cancel_data: str = "cancel",
) -> Any:
    """Build a simple confirm/cancel keyboard."""
    telegram = _load_telegram()
    return telegram.InlineKeyboardMarkup([
        [
            telegram.InlineKeyboardButton(text=confirm_text, callback_data=confirm_data),
            telegram.InlineKeyboardButton(text=cancel_text, callback_data=cancel_data),
        ]
    ])


def pagination(
    total_items: int,
    current_page: int,
    page_size: int = 5,
    prefix: str = "page",
) -> Any:
    """Build pagination navigation keyboard.

    Args:
        total_items: Total number of items.
        current_page: Current page (0-indexed).
        page_size: Items per page.
        prefix: Callback data prefix.
    """
    telegram = _load_telegram()
    total_pages = max(1, (total_items + page_size - 1) // page_size)
    buttons: list[Any] = []

    if current_page > 0:
        buttons.append(
            telegram.InlineKeyboardButton(
                text="◀️ 이전", callback_data=f"{prefix}:{current_page - 1}"
            )
        )
    buttons.append(
        telegram.InlineKeyboardButton(
            text=f"{current_page + 1}/{total_pages}", callback_data=f"{prefix}:noop"
        )
    )
    if current_page < total_pages - 1:
        buttons.append(
            telegram.InlineKeyboardButton(
                text="다음 ▶️", callback_data=f"{prefix}:{current_page + 1}"
            )
        )
    return telegram.InlineKeyboardMarkup([buttons])


def photo_type_selector() -> Any:
    """Build photo type classification keyboard for ambiguous photos."""
    telegram = _load_telegram()
    return telegram.InlineKeyboardMarkup([
        [
            telegram.InlineKeyboardButton(text="📊 운동 캡쳐", callback_data="photo_type:workout"),
            telegram.InlineKeyboardButton(text="🍽️ 식단 사진", callback_data="photo_type:food"),
        ],
        [
            telegram.InlineKeyboardButton(text="📸 기타", callback_data="photo_type:other"),
        ],
    ])
