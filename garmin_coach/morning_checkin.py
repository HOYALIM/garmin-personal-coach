"""Morning check-in — precheck (scheduled 4:45 AM)."""

import argparse
import json
import os
from datetime import date
from pathlib import Path
from statistics import median
from typing import Any

from garmin_coach.activity_fetch import fetch_morning_metrics, resume_garth
from garmin_coach.coach_engine import evaluate
from garmin_coach.models import MorningMetrics, Phase
from garmin_coach.plan import get_planned_session


BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
SNAPSHOT_DIR = DATA_DIR / "snapshots"
BASELINE_FILE = DATA_DIR / "baseline.json"


def ensure_dirs() -> None:
    SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)


def load_baseline() -> dict[str, Any]:
    if BASELINE_FILE.exists():
        return json.loads(BASELINE_FILE.read_text())
    return {"rhr_history": []}


def save_baseline(baseline: dict[str, Any]) -> None:
    BASELINE_FILE.write_text(json.dumps(baseline, indent=2))


def update_baseline(
    baseline: dict[str, Any], resting_hr: int | None, target_date: str
) -> dict[str, Any]:
    history = baseline.get("rhr_history", [])
    if resting_hr is not None:
        history = [h for h in history if h.get("date") != target_date]
        history.append({"date": target_date, "value": resting_hr})
    history = history[-14:]
    baseline["rhr_history"] = history
    return baseline


def compute_rhr_baseline(baseline: dict[str, Any]) -> float | None:
    values = [
        item.get("value")
        for item in baseline.get("rhr_history", [])
        if isinstance(item.get("value"), (int, float))
    ]
    if not values:
        return None
    return float(median(values[-7:]))


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Garmin morning check-in")
    p.add_argument("--date", default=date.today().isoformat())
    p.add_argument("--soreness", type=int, default=int(os.getenv("RUN_SORENESS", "2")))
    p.add_argument("--pain", action="store_true")
    p.add_argument("--illness", action="store_true")
    p.add_argument("--phase", choices=["precheck", "final"], default="precheck")
    return p.parse_args()


def main() -> None:
    args = parse_args()
    ensure_dirs()
    if not resume_garth():
        raise SystemExit(
            "No Garmin session. Run: pip install garth && garth login your@email.com"
        )

    raw = fetch_morning_metrics(args.date)
    resting_hr = raw["resting_hr"]
    baseline = load_baseline()
    rhr_baseline = compute_rhr_baseline(baseline)
    week_number, planned = get_planned_session(args.date)

    metrics = MorningMetrics(
        sleep_hours=raw["sleep_hours"],
        resting_hr=resting_hr,
        body_battery=raw["body_battery"],
        training_readiness=raw["training_readiness"],
        hrv_status=raw["hrv_status"],
        raw=raw,
    )

    phase = Phase.PRECHECK if args.phase == "precheck" else Phase.FINAL
    result = evaluate(
        date=args.date,
        phase=phase,
        week_number=week_number,
        planned=planned,
        metrics=metrics,
        rhr_baseline=rhr_baseline,
        soreness=args.soreness,
        pain=args.pain,
        illness=args.illness,
    )

    out_file = SNAPSHOT_DIR / f"{args.date}.json"
    out_file.write_text(json.dumps(result.to_snapshot(), ensure_ascii=False, indent=2))
    baseline = update_baseline(baseline, resting_hr, args.date)
    save_baseline(baseline)
    print(result.format_message())


if __name__ == "__main__":
    main()
