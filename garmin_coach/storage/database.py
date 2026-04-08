from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from garmin_coach.adapters.garmin.auth import redact_sensitive_fields


DEFAULT_USER_ID = "default"
SENSITIVE_KEY_TOKENS = ("password", "token", "secret", "authorization")


class GarminCoachDatabase:
    def __init__(self, db_path: str | Path):
        self.db_path = str(db_path)
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
        self._init_schema()

    def _init_schema(self) -> None:
        cur = self.conn.cursor()
        cur.execute("PRAGMA journal_mode=WAL")
        cur.execute("CREATE TABLE IF NOT EXISTS schema_version (version INTEGER NOT NULL)")
        self._ensure_v2_table(
            "daily_health",
            "CREATE TABLE daily_health (user_id TEXT NOT NULL, date TEXT NOT NULL, payload TEXT NOT NULL, PRIMARY KEY(user_id, date))",
            ["user_id", "date", "payload"],
            [
                "INSERT OR REPLACE INTO daily_health(user_id, date, payload) SELECT 'default', date, payload FROM __old_daily_health"
            ],
        )
        self._ensure_v2_table(
            "activities",
            "CREATE TABLE activities (user_id TEXT NOT NULL, activity_id TEXT NOT NULL, activity_date TEXT NOT NULL, payload TEXT NOT NULL, PRIMARY KEY(user_id, activity_id))",
            ["user_id", "activity_id", "activity_date", "payload"],
            [
                "INSERT OR REPLACE INTO activities(user_id, activity_id, activity_date, payload) SELECT 'default', activity_id, COALESCE(activity_date, ''), payload FROM __old_activities"
            ],
        )
        self._ensure_v2_table(
            "training_load",
            "CREATE TABLE training_load (user_id TEXT NOT NULL, date TEXT NOT NULL, payload TEXT NOT NULL, PRIMARY KEY(user_id, date))",
            ["user_id", "date", "payload"],
            [
                "INSERT OR REPLACE INTO training_load(user_id, date, payload) SELECT 'default', date, payload FROM __old_training_load"
            ],
        )
        self._ensure_v2_table(
            "readiness",
            "CREATE TABLE readiness (user_id TEXT NOT NULL, date TEXT NOT NULL, payload TEXT NOT NULL, PRIMARY KEY(user_id, date))",
            ["user_id", "date", "payload"],
            [
                "INSERT OR REPLACE INTO readiness(user_id, date, payload) SELECT 'default', date, payload FROM __old_readiness"
            ],
        )
        self._ensure_v2_table(
            "feedback",
            "CREATE TABLE feedback (user_id TEXT NOT NULL, feedback_id TEXT NOT NULL, activity_date TEXT NOT NULL, payload TEXT NOT NULL, PRIMARY KEY(user_id, feedback_id))",
            ["user_id", "feedback_id", "activity_date", "payload"],
            [
                "INSERT OR REPLACE INTO feedback(user_id, feedback_id, activity_date, payload) SELECT 'default', feedback_id, activity_date, payload FROM __old_feedback"
            ],
        )
        self._ensure_v2_table(
            "nutrition_log",
            "CREATE TABLE nutrition_log (user_id TEXT NOT NULL, entry_id TEXT NOT NULL, entry_date TEXT NOT NULL, payload TEXT NOT NULL, PRIMARY KEY(user_id, entry_id))",
            ["user_id", "entry_id", "entry_date", "payload"],
            [
                "INSERT OR REPLACE INTO nutrition_log(user_id, entry_id, entry_date, payload) SELECT 'default', entry_id, entry_date, payload FROM __old_nutrition_log"
            ],
        )
        if cur.execute("SELECT COUNT(*) FROM schema_version").fetchone()[0] == 0:
            cur.execute("INSERT INTO schema_version(version) VALUES (2)")
        else:
            cur.execute("UPDATE schema_version SET version = 2")
        self.conn.commit()

    def _ensure_v2_table(
        self,
        table_name: str,
        create_sql: str,
        expected_columns: list[str],
        migration_sql: list[str],
    ) -> None:
        info = self.conn.execute(f"PRAGMA table_info({table_name})").fetchall()
        if not info:
            self.conn.execute(create_sql)
            return
        existing_columns = [row[1] for row in info]
        if existing_columns == expected_columns:
            return
        backup_name = f"__old_{table_name}"
        self.conn.execute(f"ALTER TABLE {table_name} RENAME TO {backup_name}")
        self.conn.execute(create_sql)
        for stmt in migration_sql:
            self.conn.execute(stmt)
        self.conn.execute(f"DROP TABLE {backup_name}")

    def _serialize_payload(self, payload: dict[str, Any]) -> str:
        self._assert_secret_free_payload(payload)
        return json.dumps(redact_sensitive_fields(payload), ensure_ascii=False, sort_keys=True)

    def _assert_secret_free_payload(self, payload: dict[str, Any]) -> None:
        stack: list[Any] = [payload]
        while stack:
            current = stack.pop()
            if isinstance(current, dict):
                for key, value in current.items():
                    lowered = key.lower()
                    if any(token in lowered for token in SENSITIVE_KEY_TOKENS):
                        raise ValueError(f"Refusing to persist sensitive field: {key}")
                    if isinstance(value, (dict, list, tuple)):
                        stack.append(value)
            elif isinstance(current, (list, tuple)):
                for value in current:
                    if isinstance(value, (dict, list, tuple)):
                        stack.append(value)

    def save_daily_health(self, user_id: str, metric_date: str, payload: dict[str, Any]) -> None:
        self.conn.execute(
            "INSERT INTO daily_health(user_id, date, payload) VALUES (?, ?, ?) ON CONFLICT(user_id, date) DO UPDATE SET payload=excluded.payload",
            (user_id, metric_date, self._serialize_payload(payload)),
        )
        self.conn.commit()

    def load_daily_health(self, user_id: str, metric_date: str) -> dict[str, Any] | None:
        row = self.conn.execute(
            "SELECT payload FROM daily_health WHERE user_id = ? AND date = ?",
            (user_id, metric_date),
        ).fetchone()
        return json.loads(row[0]) if row else None

    def save_activity(
        self, user_id: str, activity_id: str, activity_date: str, payload: dict[str, Any]
    ) -> None:
        self.conn.execute(
            "INSERT INTO activities(user_id, activity_id, activity_date, payload) VALUES (?, ?, ?, ?) ON CONFLICT(user_id, activity_id) DO UPDATE SET activity_date=excluded.activity_date, payload=excluded.payload",
            (user_id, activity_id, activity_date, self._serialize_payload(payload)),
        )
        self.conn.commit()

    def load_activity(self, user_id: str, activity_id: str) -> dict[str, Any] | None:
        row = self.conn.execute(
            "SELECT payload FROM activities WHERE user_id = ? AND activity_id = ?",
            (user_id, activity_id),
        ).fetchone()
        return json.loads(row[0]) if row else None

    def list_recent_activities(self, user_id: str, limit: int = 7) -> list[dict[str, Any]]:
        rows = self.conn.execute(
            "SELECT payload FROM activities WHERE user_id = ? ORDER BY activity_date DESC LIMIT ?",
            (user_id, limit),
        ).fetchall()
        return [json.loads(row[0]) for row in rows]

    def save_training_load(self, user_id: str, metric_date: str, payload: dict[str, Any]) -> None:
        self.conn.execute(
            "INSERT INTO training_load(user_id, date, payload) VALUES (?, ?, ?) ON CONFLICT(user_id, date) DO UPDATE SET payload=excluded.payload",
            (user_id, metric_date, self._serialize_payload(payload)),
        )
        self.conn.commit()

    def load_training_load(self, user_id: str, metric_date: str) -> dict[str, Any] | None:
        row = self.conn.execute(
            "SELECT payload FROM training_load WHERE user_id = ? AND date = ?",
            (user_id, metric_date),
        ).fetchone()
        return json.loads(row[0]) if row else None

    def save_readiness(self, user_id: str, metric_date: str, payload: dict[str, Any]) -> None:
        self.conn.execute(
            "INSERT INTO readiness(user_id, date, payload) VALUES (?, ?, ?) ON CONFLICT(user_id, date) DO UPDATE SET payload=excluded.payload",
            (user_id, metric_date, self._serialize_payload(payload)),
        )
        self.conn.commit()

    def load_readiness(self, user_id: str, metric_date: str) -> dict[str, Any] | None:
        row = self.conn.execute(
            "SELECT payload FROM readiness WHERE user_id = ? AND date = ?",
            (user_id, metric_date),
        ).fetchone()
        return json.loads(row[0]) if row else None

    def list_recent_daily_health(self, user_id: str, limit: int = 7) -> list[dict[str, Any]]:
        rows = self.conn.execute(
            "SELECT payload FROM daily_health WHERE user_id = ? ORDER BY date DESC LIMIT ?",
            (user_id, limit),
        ).fetchall()
        return [json.loads(row[0]) for row in rows]

    def save_feedback(
        self, user_id: str, feedback_id: str, activity_date: str, payload: dict[str, Any]
    ) -> None:
        self.conn.execute(
            "INSERT INTO feedback(user_id, feedback_id, activity_date, payload) VALUES (?, ?, ?, ?) ON CONFLICT(user_id, feedback_id) DO UPDATE SET activity_date=excluded.activity_date, payload=excluded.payload",
            (user_id, feedback_id, activity_date, self._serialize_payload(payload)),
        )
        self.conn.commit()

    def load_feedback(self, user_id: str, feedback_id: str) -> dict[str, Any] | None:
        row = self.conn.execute(
            "SELECT payload FROM feedback WHERE user_id = ? AND feedback_id = ?",
            (user_id, feedback_id),
        ).fetchone()
        return json.loads(row[0]) if row else None

    def list_feedback(
        self,
        user_id: str,
        *,
        limit: int | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> list[dict[str, Any]]:
        clauses = ["user_id = ?"]
        params: list[Any] = [user_id]
        if start_date is not None:
            clauses.append("activity_date >= ?")
            params.append(start_date)
        if end_date is not None:
            clauses.append("activity_date <= ?")
            params.append(end_date)
        sql = f"SELECT payload FROM feedback WHERE {' AND '.join(clauses)} ORDER BY activity_date DESC, feedback_id DESC"
        if limit is not None:
            sql += " LIMIT ?"
            params.append(limit)
        rows = self.conn.execute(sql, params).fetchall()
        return [json.loads(row[0]) for row in rows]

    def save_nutrition_log(
        self, user_id: str, entry_id: str, entry_date: str, payload: dict[str, Any]
    ) -> None:
        self.conn.execute(
            "INSERT INTO nutrition_log(user_id, entry_id, entry_date, payload) VALUES (?, ?, ?, ?) ON CONFLICT(user_id, entry_id) DO UPDATE SET entry_date=excluded.entry_date, payload=excluded.payload",
            (user_id, entry_id, entry_date, self._serialize_payload(payload)),
        )
        self.conn.commit()

    def load_nutrition_log(self, user_id: str, entry_id: str) -> dict[str, Any] | None:
        row = self.conn.execute(
            "SELECT payload FROM nutrition_log WHERE user_id = ? AND entry_id = ?",
            (user_id, entry_id),
        ).fetchone()
        return json.loads(row[0]) if row else None

    def list_recent_nutrition_logs(self, user_id: str, limit: int = 20) -> list[dict[str, Any]]:
        rows = self.conn.execute(
            "SELECT payload FROM nutrition_log WHERE user_id = ? ORDER BY entry_date DESC, entry_id DESC LIMIT ?",
            (user_id, limit),
        ).fetchall()
        return [json.loads(row[0]) for row in rows]

    def close(self) -> None:
        self.conn.close()
