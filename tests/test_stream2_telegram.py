import asyncio
from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace


def _fake_telegram_modules():
    class InlineKeyboardButton:
        def __init__(self, text, callback_data):
            self.text = text
            self.callback_data = callback_data

    class InlineKeyboardMarkup:
        def __init__(self, rows):
            self.inline_keyboard = rows

    class BotCommand:
        def __init__(self, command, description):
            self.command = command
            self.description = description

    class CommandHandler:
        def __init__(self, command, callback):
            self.command = command
            self.callback = callback

    class CallbackQueryHandler:
        def __init__(self, callback):
            self.callback = callback

    class MessageHandler:
        def __init__(self, filters, callback):
            self.filters = filters
            self.callback = callback

    class FakeFilter:
        def __and__(self, other):
            return self

        def __invert__(self):
            return self

    filters = SimpleNamespace(TEXT=FakeFilter(), COMMAND=FakeFilter(), PHOTO=FakeFilter())

    telegram = SimpleNamespace(
        InlineKeyboardButton=InlineKeyboardButton,
        InlineKeyboardMarkup=InlineKeyboardMarkup,
        BotCommand=BotCommand,
        Update=SimpleNamespace(ALL_TYPES=("message", "callback_query")),
    )
    telegram_ext = SimpleNamespace(
        CommandHandler=CommandHandler,
        CallbackQueryHandler=CallbackQueryHandler,
        MessageHandler=MessageHandler,
        filters=filters,
    )
    return telegram, telegram_ext


class FakeBot:
    def __init__(self):
        self.messages = []
        self.photos = []
        self.commands = []

    async def send_message(self, chat_id, text, reply_markup=None, parse_mode=None):
        self.messages.append(
            {
                "chat_id": chat_id,
                "text": text,
                "reply_markup": reply_markup,
                "parse_mode": parse_mode,
            }
        )

    async def send_photo(self, chat_id, photo, caption=None):
        self.photos.append({"chat_id": chat_id, "photo": photo, "caption": caption})

    async def set_my_commands(self, commands):
        self.commands = commands


class FakeJob:
    def __init__(self, name=None, data=None, time=None, callback=None):
        self.name = name
        self.data = data
        self.time = time
        self.callback = callback
        self.removed = False

    def schedule_removal(self):
        self.removed = True


class FakeJobQueue:
    def __init__(self):
        self.jobs = []

    def run_daily(self, callback, time, name, days=None, data=None):
        self.jobs.append(FakeJob(name=name, data=data, time=time, callback=callback))

    def run_monthly(self, callback, when, day, name, data=None):
        self.jobs.append(FakeJob(name=name, time=when, data=data, callback=callback))

    def run_repeating(self, callback, interval, first, name):
        self.jobs.append(
            FakeJob(name=name, data={"interval": interval, "first": first}, callback=callback)
        )

    def get_jobs_by_name(self, name):
        return [job for job in self.jobs if job.name == name]


class FakeApplication:
    def __init__(self):
        self.bot = FakeBot()
        self.handlers = []
        self.job_queue = FakeJobQueue()
        self.bot_data = {}
        self.created_coroutines = []
        self.post_init = None

    def add_handler(self, handler):
        self.handlers.append(handler)

    def create_task(self, coroutine):
        self.created_coroutines.append(coroutine)

    def run_polling(self, **kwargs):
        self.polling_kwargs = kwargs

    def run_webhook(self, **kwargs):
        self.webhook_kwargs = kwargs


def test_adapter_splits_long_messages(monkeypatch):
    from garmin_coach.interfaces.telegram import adapter as adapter_module

    monkeypatch.setattr(adapter_module, "_load_telegram", _fake_telegram_modules)
    adapter = adapter_module.TelegramAdapter(FakeBot())

    long_line = "A" * 4199
    chunks = adapter._split_message(long_line)

    assert "".join(chunks) == long_line
    assert max(len(chunk) for chunk in chunks) <= 4096

    markdown_heavy = "*bold*_item_[link](x)!\n" * 240
    markdown_chunks = adapter._split_message(markdown_heavy)
    assert "".join(markdown_chunks) == markdown_heavy
    assert max(len(chunk) for chunk in markdown_chunks) <= 4096


def test_adapter_send_message_keeps_escaped_chunks_under_limit(monkeypatch):
    from garmin_coach.interfaces.telegram import adapter as adapter_module

    monkeypatch.setattr(adapter_module, "_load_telegram", _fake_telegram_modules)
    bot = FakeBot()
    adapter = adapter_module.TelegramAdapter(bot)

    text = "_*[]()~`>#+-=|{}.!\\\n" * 250
    asyncio.run(adapter.send_message("42", text))

    assert bot.messages
    assert all(len(message["text"]) <= 4096 for message in bot.messages)
    assert all(message["parse_mode"] == "MarkdownV2" for message in bot.messages)
    assert all(not message["text"].endswith("\\") for message in bot.messages)


def test_request_select_retries_prompt_send(monkeypatch):
    from garmin_coach.interfaces.telegram import adapter as adapter_module
    from garmin_coach.ports import Option

    monkeypatch.setattr(adapter_module, "_load_telegram", _fake_telegram_modules)

    class FlakyBot(FakeBot):
        def __init__(self):
            super().__init__()
            self.calls = 0

        async def send_message(self, chat_id, text, reply_markup=None, parse_mode=None):
            self.calls += 1
            if self.calls == 1:
                raise RuntimeError("temporary")
            await super().send_message(chat_id, text, reply_markup, parse_mode)

    bot = FlakyBot()
    adapter = adapter_module.TelegramAdapter(bot)

    async def fake_wait(user_id):
        return "opt:chosen"

    adapter._wait_for_input = fake_wait
    result = asyncio.run(adapter.request_select("42", "pick", [Option(label="A", value="chosen")]))
    assert result == "chosen"
    assert bot.calls == 2


def test_request_number_timeout_is_explicit(monkeypatch):
    from garmin_coach.interfaces.telegram import adapter as adapter_module
    from garmin_coach.ports import InputAbortReason, InputAborted

    monkeypatch.setattr(adapter_module, "_load_telegram", _fake_telegram_modules)
    adapter = adapter_module.TelegramAdapter(FakeBot())

    async def fake_wait(user_id):
        return None

    adapter._wait_for_input = fake_wait
    try:
        asyncio.run(adapter.request_number("42", "num", 1, 10))
        raise AssertionError("expected InputAborted")
    except InputAborted as exc:
        assert exc.reason == InputAbortReason.TIMEOUT


def test_request_photo_skip_is_explicit(monkeypatch):
    from garmin_coach.interfaces.telegram import adapter as adapter_module
    from garmin_coach.ports import InputAbortReason, InputAborted

    monkeypatch.setattr(adapter_module, "_load_telegram", _fake_telegram_modules)
    adapter = adapter_module.TelegramAdapter(FakeBot())

    async def fake_wait(user_id):
        return "photo:skip"

    adapter._wait_for_input = fake_wait
    try:
        asyncio.run(adapter.request_photo("42", "photo"))
        raise AssertionError("expected InputAborted")
    except InputAborted as exc:
        assert exc.reason == InputAbortReason.SKIPPED


def test_scheduler_delivers_reports_and_normalizes_activity():
    from garmin_coach.interfaces.telegram.scheduler import TelegramScheduler

    calls = []
    sent = []

    class FakePostWorkout:
        async def execute(self, user_id, activity):
            calls.append((user_id, activity))

    class FakeReports:
        async def generate_weekly(self, user_id):
            return {
                "period": "W",
                "summary": {"sessions": 1},
                "training_load": {},
                "recovery": {},
                "coach_comment": "ok",
            }

        async def generate_monthly(self, user_id):
            return {
                "period": "M",
                "summary": {"sessions": 2},
                "training_load": {},
                "recovery": {},
                "coach_comment": "ok",
            }

    class FakeDelivery:
        async def send_message(self, user_id, text):
            sent.append((user_id, text))

    class FakeUserConfig:
        async def get_schedule_config(self, user_id):
            return {}

        async def get_all_user_ids(self):
            return ["11", "22"]

    scheduler = TelegramScheduler(
        SimpleNamespace(post_workout=FakePostWorkout()),
        user_config=FakeUserConfig(),
        delivery=FakeDelivery(),
        reports=FakeReports(),
    )

    asyncio.run(scheduler._weekly_report_job(SimpleNamespace(job=None)))
    asyncio.run(scheduler._monthly_report_job(SimpleNamespace(job=None)))
    asyncio.run(
        scheduler.on_new_activity(
            SimpleNamespace(activity_id="abc", type="run", duration_min=42, avg_hr=150),
            user_id="11",
        )
    )

    assert sent
    assert any(user_id == "11" and "주간 트레이닝 리포트" in text for user_id, text in sent)
    assert any(user_id == "22" and "주간 트레이닝 리포트" in text for user_id, text in sent)
    assert any(user_id == "11" and "월간 트레이닝 리포트" in text for user_id, text in sent)
    assert any(user_id == "22" and "월간 트레이닝 리포트" in text for user_id, text in sent)
    assert calls == [
        ("11", {"activity_id": "abc", "type": "run", "duration_min": 42, "avg_hr": 150})
    ]


def test_scheduler_scopes_weekly_and_monthly_jobs_to_user():
    from garmin_coach.interfaces.telegram.scheduler import TelegramScheduler

    sent = []

    class FakeReports:
        async def generate_weekly(self, user_id):
            return {
                "period": "W",
                "summary": {"sessions": 1},
                "training_load": {},
                "recovery": {},
                "coach_comment": user_id,
            }

        async def generate_monthly(self, user_id):
            return {
                "period": "M",
                "summary": {"sessions": 1},
                "training_load": {},
                "recovery": {},
                "coach_comment": user_id,
            }

    class FakeDelivery:
        async def send_message(self, user_id, text):
            sent.append((user_id, text))

    class FakeUserConfig:
        async def get_schedule_config(self, user_id):
            return {"weekly_time": "20:00", "monthly_time": "09:00", "timezone": "Asia/Seoul"}

        async def get_all_user_ids(self):
            return ["u1", "u2"]

    scheduler = TelegramScheduler(
        SimpleNamespace(),
        user_config=FakeUserConfig(),
        delivery=FakeDelivery(),
        reports=FakeReports(),
    )
    queue = FakeJobQueue()
    scheduler.setup(queue)
    asyncio.run(scheduler.schedule_for_user("u1"))
    asyncio.run(scheduler.schedule_for_user("u2"))

    weekly_u1 = next(job for job in queue.jobs if job.name == "weekly_u1")
    monthly_u2 = next(job for job in queue.jobs if job.name == "monthly_u2")
    before_weekly = len(sent)
    asyncio.run(weekly_u1.callback(SimpleNamespace(job=weekly_u1)))
    weekly_sent = sent[before_weekly:]
    assert weekly_sent and all(user_id == "u1" for user_id, _ in weekly_sent)

    before_monthly = len(sent)
    asyncio.run(monthly_u2.callback(SimpleNamespace(job=monthly_u2)))
    monthly_sent = sent[before_monthly:]
    assert monthly_sent and all(user_id == "u2" for user_id, _ in monthly_sent)


def test_scheduler_and_event_paths_share_user_lock():
    from garmin_coach.interfaces.telegram.scheduler import TelegramScheduler

    overlap = {"active": False, "saw_overlap": False}

    class FakeLocker:
        def __init__(self):
            self.locks = {}

        def get_user_lock(self, user_id):
            self.locks.setdefault(user_id, asyncio.Lock())
            return self.locks[user_id]

    class FakeMorning:
        async def execute(self, user_id):
            if overlap["active"]:
                overlap["saw_overlap"] = True
            overlap["active"] = True
            await asyncio.sleep(0.01)
            overlap["active"] = False

    class FakePostWorkout:
        async def execute(self, user_id, activity):
            if overlap["active"]:
                overlap["saw_overlap"] = True
            overlap["active"] = True
            await asyncio.sleep(0.01)
            overlap["active"] = False

    class FakeUserConfig:
        async def get_schedule_config(self, user_id):
            return {}

        async def get_all_user_ids(self):
            return ["u1"]

    scheduler = TelegramScheduler(
        SimpleNamespace(morning_briefing=FakeMorning(), post_workout=FakePostWorkout()),
        user_config=FakeUserConfig(),
        locker=FakeLocker(),
    )

    async def run_both():
        await asyncio.gather(
            scheduler._morning_briefing_job(
                SimpleNamespace(job=SimpleNamespace(data={"user_id": "u1"}))
            ),
            scheduler.on_new_activity({"activity_id": "a1"}, user_id="u1"),
        )

    asyncio.run(run_both())
    assert overlap["saw_overlap"] is False


def test_settings_timeout_does_not_persist_fake_values():
    from garmin_coach.flows.settings import SettingsFlow
    from garmin_coach.ports import (
        CoachingPort,
        InputAbortReason,
        InputAborted,
        InputType,
    )

    updates = []

    class FakeService:
        async def has_profile(self, user_id):
            return True

        async def summarize_settings(self, user_id):
            return "settings"

        async def update_profile_name(self, user_id, value):
            updates.append(("name", value))

        async def update_weight(self, user_id, value):
            updates.append(("weight", value))

        async def update_available_days(self, user_id, value):
            updates.append(("days", value))

        async def update_schedule(self, user_id, field, value):
            updates.append((field, value))

        async def update_nutrition(self, user_id, weight_goal, dietary_style):
            updates.append(("nutrition", weight_goal, dietary_style))

        async def update_medical(self, user_id, beta_blocker, current_injuries, notes):
            updates.append(("medical", beta_blocker, current_injuries, notes))

        async def update_sleep(self, user_id, bedtime, wake_time, issues):
            updates.append(("sleep", bedtime, wake_time, issues))

        async def update_preferences(
            self,
            user_id,
            preferred_training_time,
            cross_training_preferences,
            notification_frequency,
            units,
            timezone,
            strava_connected,
        ):
            updates.append(
                (
                    "preferences",
                    preferred_training_time,
                    cross_training_preferences,
                    notification_frequency,
                    units,
                    timezone,
                    strava_connected,
                )
            )

        async def update_ai_tone(self, user_id, tone):
            updates.append(("tone", tone))

    class FakePort(CoachingPort):
        def __init__(self):
            self.messages = []

        async def send_message(self, user_id, text, buttons=None):
            self.messages.append(text)

        async def send_image(self, user_id, image, caption=None):
            return None

        async def send_report(self, user_id, report):
            return None

        async def request_text(self, user_id, prompt):
            raise InputAborted(InputType.TEXT, InputAbortReason.TIMEOUT)

        async def request_number(self, user_id, prompt, min_val=None, max_val=None):
            raise InputAborted(InputType.NUMBER, InputAbortReason.TIMEOUT)

        async def request_date(self, user_id, prompt):
            raise InputAborted(InputType.DATE, InputAbortReason.TIMEOUT)

        async def request_select(self, user_id, prompt, options):
            if prompt == "settings":
                return "profile"
            raise InputAborted(InputType.SELECT, InputAbortReason.TIMEOUT)

        async def request_multi_select(self, user_id, prompt, options):
            raise InputAborted(InputType.MULTI_SELECT, InputAbortReason.TIMEOUT)

        async def request_photo(self, user_id, prompt):
            raise InputAborted(InputType.PHOTO, InputAbortReason.TIMEOUT)

    port = FakePort()
    asyncio.run(SettingsFlow(port, FakeService()).execute("u1"))
    assert updates == []
    assert any("시간이 초과" in msg for msg in port.messages)


def test_morning_actions_persist_state():
    from garmin_coach.flows.morning_briefing import MorningBriefingFlow
    from garmin_coach.ports import CoachingPort

    events = []

    class FakePort(CoachingPort):
        async def send_message(self, user_id, text, buttons=None):
            events.append(("send", text))

        async def send_image(self, user_id, image, caption=None):
            return None

        async def send_report(self, user_id, report):
            return None

        async def request_text(self, user_id, prompt):
            return ""

        async def request_number(self, user_id, prompt, min_val=None, max_val=None):
            return 0.0

        async def request_date(self, user_id, prompt):
            from datetime import date

            return date.today()

        async def request_select(self, user_id, prompt, options):
            return "tempo"

        async def request_multi_select(self, user_id, prompt, options):
            return []

        async def request_photo(self, user_id, prompt):
            return None

    class FakeReadiness:
        async def get_readiness(self, user_id):
            return {}

    class FakeCoaching:
        async def generate_daily_coaching(self, user_id, readiness):
            return {}

    class FakeState:
        async def change_today_session(self, user_id, session_type):
            events.append(("change", session_type))

        async def postpone_today(self, user_id):
            events.append(("postpone", True))

    flow = MorningBriefingFlow(
        FakePort(), readiness=FakeReadiness(), coaching=FakeCoaching(), plan_state=FakeState()
    )
    asyncio.run(flow.handle_response("u1", "morning:change"))
    asyncio.run(flow.handle_response("u1", "morning:postpone"))
    assert ("change", "tempo") in events
    assert ("postpone", True) in events


def test_morning_state_affects_runtime_providers(tmp_path):
    import garmin_coach.telegram_bot as telegram_bot
    from garmin_coach.models.coaching import DayPlan, SessionType, WeeklyPlan

    store = telegram_bot._MorningPlanStateStore(tmp_path)

    class FakeBridge:
        async def create_daily_coaching(self, user_id, readiness):
            from garmin_coach.models.coaching import CoachingResponse

            return CoachingResponse(text="base", intensity="easy", session_type=SessionType.EASY)

        async def create_weekly_plan(self, user_id):
            from datetime import date, timedelta

            tomorrow = date.today() + timedelta(days=1)
            return WeeklyPlan(
                days=[
                    DayPlan(
                        date=tomorrow.isoformat(),
                        session_type=SessionType.TEMPO,
                        description="Tempo Run",
                    )
                ]
            )

    coaching = telegram_bot._DailyCoachingProvider(FakeBridge(), store)
    asyncio.run(store.postpone_today("u1"))
    response = asyncio.run(coaching.generate_daily_coaching("u1", {}))
    assert response.session_type == SessionType.REST

    tomorrow_provider = telegram_bot._TomorrowPlanProvider(FakeBridge(), object(), store)
    tomorrow = asyncio.run(tomorrow_provider.get_tomorrow_plan("u1"))
    assert tomorrow["session"] == "미뤄둔 오늘 세션 재진행"


def test_schedule_config_reads_timezone_from_profile_file(tmp_path):
    import garmin_coach.telegram_bot as telegram_bot
    import yaml

    class TestService(telegram_bot._UserProfileService):
        def _manager(self, user_id):
            return SimpleNamespace(config_path=tmp_path / f"{user_id}.yaml", load=lambda: None)

    service = TestService()
    (tmp_path / "u1.yaml").write_text(yaml.safe_dump({"timezone": "Europe/Paris"}))
    config = asyncio.run(service.get_schedule_config("u1"))
    assert config["timezone"] == "Europe/Paris"


def test_pre_workout_advice_depends_on_session_type():
    import garmin_coach.telegram_bot as telegram_bot

    class FakeProfileService:
        def _load(self, user_id):
            return SimpleNamespace(
                profile=SimpleNamespace(primary_sport=SimpleNamespace(value="running"))
            )

    bridge = telegram_bot._RuntimeDataBridge(
        FakeProfileService(), telegram_bot.GarminCoachDatabase(":memory:")
    )
    provider = telegram_bot._PreWorkoutNutritionProvider(bridge)
    easy = asyncio.run(provider.get_pre_workout_advice("u1", "easy"))
    long_run = asyncio.run(provider.get_pre_workout_advice("u1", "long"))
    assert easy is not None
    assert long_run is not None
    assert easy["description"] != long_run["description"]


def test_onboarding_resumes_from_saved_progress():
    from garmin_coach.flows.onboarding import OnboardingFlow
    from garmin_coach.ports import CoachingPort

    created = {}

    class FakeService:
        def __init__(self):
            self.progress = {
                "garmin_email": "runner@example.com",
                "garmin_connected": True,
                "name": "Hoyeon",
                "age": 31,
                "sex": "female",
            }

        async def has_profile(self, user_id):
            return False

        async def summarize_profile(self, user_id):
            return ""

        async def connect_garmin(self, user_id, email, password):
            return True

        async def create_profile(self, user_id, payload):
            created.update(payload)
            return "done"

        async def update_profile_sections(self, user_id, payload):
            return None

        async def load_progress(self, user_id):
            return dict(self.progress)

        async def save_progress(self, user_id, payload):
            self.progress = dict(payload)

        async def clear_progress(self, user_id):
            self.progress = {}

    class FakePort(CoachingPort):
        def __init__(self):
            self.messages = []

        async def send_message(self, user_id, text, buttons=None):
            self.messages.append(text)

        async def send_image(self, user_id, image, caption=None):
            return None

        async def send_report(self, user_id, report):
            return None

        async def request_text(self, user_id, prompt):
            if "이름" in prompt:
                raise AssertionError("name prompt should not repeat")
            if "목표 대회" in prompt:
                return "Seoul Marathon"
            if "아침 브리핑" in prompt:
                return "06:30"
            if "저녁 체크인" in prompt:
                return "21:30"
            return "없음"

        async def request_number(self, user_id, prompt, min_val=None, max_val=None):
            if "나이" in prompt:
                raise AssertionError("age prompt should not repeat")
            if "키" in prompt:
                return 171
            if "체중" in prompt:
                return 63
            if "주당 훈련 가능" in prompt:
                return 5
            return 0

        async def request_date(self, user_id, prompt):
            from datetime import date

            return date(2026, 11, 1)

        async def request_select(self, user_id, prompt, options):
            if "성별" in prompt:
                raise AssertionError("sex prompt should not repeat")
            if "목표 날짜가 있나요" in prompt:
                return "yes"
            if "현재 운동 수준" in prompt:
                return "intermediate"
            if "체중/체성분 목표" in prompt:
                return "maintain"
            if "식단 스타일" in prompt:
                return "omnivore"
            return options[0].value

        async def request_multi_select(self, user_id, prompt, options):
            return ["running"]

        async def request_photo(self, user_id, prompt):
            return None

    service = FakeService()
    port = FakePort()
    asyncio.run(OnboardingFlow(port, service).execute("u1"))
    assert created["garmin_email"] == "runner@example.com"
    assert created["garmin_connected"] is True
    assert created["name"] == "Hoyeon"
    assert created["age"] == 31
    assert created["sex"] == "female"
    assert service.progress == {}
    assert any("이어서 진행" in message for message in port.messages)


def test_user_profile_service_stores_garmin_connection(tmp_path):
    import garmin_coach.telegram_bot as telegram_bot

    class TestService(telegram_bot._UserProfileService):
        def _manager(self, user_id):
            from garmin_coach.profile_manager import ProfileManager

            return ProfileManager(config_path=tmp_path / f"{user_id}.yaml")

    service = TestService()
    asyncio.run(
        service.create_profile(
            "u1",
            {
                "garmin_email": "runner@example.com",
                "garmin_connected": True,
                "name": "Runner",
                "age": 30,
                "sex": "female",
                "height_cm": 165.0,
                "weight_kg": 55.0,
                "sports": ["running"],
                "goal_event": "",
                "goal_date": "",
                "fitness_level": "intermediate",
                "available_days": 4,
                "morning_time": "06:00",
                "evening_time": "22:00",
                "weight_goal": "maintain",
                "dietary_style": "omnivore",
            },
        )
    )
    profile = service._load("u1")
    assert profile.garmin.email == "runner@example.com"
    assert profile.garmin.connected is True


def test_flows_remain_isolated_from_telegram_imports():
    flows_dir = Path("/Users/ho/code/garmin-personal-coach/garmin_coach/flows")
    for path in flows_dir.glob("*.py"):
        lines = path.read_text().splitlines()
        imports = [line.strip() for line in lines if line.strip().startswith(("import ", "from "))]
        joined = "\n".join(imports)
        assert "from telegram import" not in joined
        assert "import telegram" not in joined
        assert "from garmin_coach.interfaces" not in joined
        assert "import garmin_coach.interfaces" not in joined
        assert "from garmin_coach.profile_manager" not in joined
        assert "import garmin_coach.profile_manager" not in joined


def test_scheduler_uses_asia_seoul_timezone_for_user_jobs():
    from garmin_coach.interfaces.telegram.scheduler import TelegramScheduler

    class FakeUserConfig:
        async def get_schedule_config(self, user_id):
            return {"morning_time": "06:15", "evening_time": "21:45", "timezone": "Asia/Seoul"}

        async def get_all_user_ids(self):
            return [user_id]

    user_id = "timezone-user"
    scheduler = TelegramScheduler(SimpleNamespace(), user_config=FakeUserConfig())
    queue = FakeJobQueue()
    scheduler.setup(queue)
    asyncio.run(scheduler.schedule_for_user(user_id))

    morning = next(job for job in queue.jobs if job.name == f"morning_{user_id}")
    evening = next(job for job in queue.jobs if job.name == f"evening_{user_id}")
    weekly = next(job for job in queue.jobs if job.name == f"weekly_{user_id}")
    monthly = next(job for job in queue.jobs if job.name == f"monthly_{user_id}")
    assert getattr(morning.time.tzinfo, "key", None) == "Asia/Seoul"
    assert getattr(evening.time.tzinfo, "key", None) == "Asia/Seoul"
    assert getattr(weekly.time.tzinfo, "key", None) == "Asia/Seoul"
    assert getattr(monthly.time.tzinfo, "key", None) == "Asia/Seoul"


def test_build_flow_registry_uses_real_flow_classes(monkeypatch):
    import garmin_coach.telegram_bot as telegram_bot
    from garmin_coach.interfaces.telegram import adapter as adapter_module
    from garmin_coach.storage.database import GarminCoachDatabase

    telegram, telegram_ext = _fake_telegram_modules()
    monkeypatch.setattr(adapter_module, "_load_telegram", lambda: (telegram, telegram_ext))

    class FakeProfileService:
        async def has_profile(self, user_id):
            return False

        async def summarize_profile(self, user_id):
            return "summary"

        async def create_profile(self, user_id, payload):
            return "created"

        async def update_profile_sections(self, user_id, payload):
            return None

        async def load_progress(self, user_id):
            return {}

        async def save_progress(self, user_id, payload):
            return None

        async def clear_progress(self, user_id):
            return None

        async def summarize_settings(self, user_id):
            return "settings"

        async def update_profile_name(self, user_id, value):
            return None

        async def update_weight(self, user_id, value):
            return None

        async def update_available_days(self, user_id, value):
            return None

        async def update_schedule(self, user_id, field, value):
            return None

        async def update_nutrition(self, user_id, weight_goal, dietary_style):
            return None

        async def update_medical(self, user_id, beta_blocker, current_injuries, notes):
            return None

        async def update_sleep(self, user_id, bedtime, wake_time, issues):
            return None

        async def update_preferences(
            self,
            user_id,
            preferred_training_time,
            cross_training_preferences,
            notification_frequency,
            units,
            timezone,
            strava_connected,
        ):
            return None

        async def update_ai_tone(self, user_id, tone):
            return None

        async def summarize_goals(self, user_id):
            return "goals"

        async def update_goal_event(self, user_id, value):
            return None

        async def update_goal_date(self, user_id, value):
            return None

        async def update_fitness_level(self, user_id, value):
            return None

        async def update_max_weekly_hours(self, user_id, value):
            return None

        async def get_schedule_config(self, user_id):
            return {"morning_time": "07:00", "evening_time": "21:00"}

    monkeypatch.setattr(telegram_bot, "_UserProfileService", lambda: FakeProfileService())
    bridge = telegram_bot._RuntimeDataBridge(FakeProfileService(), GarminCoachDatabase(":memory:"))
    registry = telegram_bot._build_flow_registry(
        adapter_module.TelegramAdapter(FakeBot()),
        bridge,
        GarminCoachDatabase(":memory:"),
    )

    assert registry.onboarding.__class__.__name__ == "OnboardingFlow"
    assert registry.settings.__class__.__name__ == "SettingsFlow"
    assert registry.goals.__class__.__name__ == "GoalsFlow"


def test_photo_router_attempts_auto_detection():
    import garmin_coach.telegram_bot as telegram_bot
    from garmin_coach.storage.database import GarminCoachDatabase

    class FakeProfileService:
        def _load(self, user_id):
            return None

    router = telegram_bot._PhotoRouter(
        telegram_bot._RuntimeDataBridge(FakeProfileService(), GarminCoachDatabase(":memory:"))
    )
    assert asyncio.run(router.auto_detect_type(b"\x89PNGdemo")) == "workout"
    assert asyncio.run(router.auto_detect_type(b"\xff\xd8\xffdemo")) == "food"
    assert asyncio.run(router.auto_detect_type(b"raw-bytes")) is None


def test_evening_providers_use_real_inputs(monkeypatch):
    import garmin_coach.telegram_bot as telegram_bot
    from garmin_coach.storage.database import GarminCoachDatabase
    from garmin_coach.models import ActivitySummary
    from garmin_coach.models.coaching import DayPlan, SessionType, WeeklyPlan
    from garmin_coach.models.health_metrics import HealthMetrics, TrainingLoad
    from datetime import date, timedelta

    tomorrow = date.today() + timedelta(days=1)

    class FakeBridge:
        def build_health_metrics(self, user_id):
            return HealthMetrics(
                metric_date=date.today(),
                training_load=TrainingLoad(tsb=-5),
                recent_activities=[
                    ActivitySummary(
                        type="run",
                        calories=640,
                        start_time=date.today().isoformat(),
                        raw={"activity_name": "Morning Run"},
                    )
                ],
            )

        async def create_weekly_plan(self, user_id):
            return WeeklyPlan(
                days=[
                    DayPlan(
                        date=tomorrow.isoformat(),
                        session_type=SessionType.TEMPO,
                        description="Tempo Run",
                    )
                ]
            )

    monkeypatch.setattr(
        telegram_bot,
        "safe_get_daily_summary",
        lambda _: SimpleNamespace(total_steps=12345, average_stress_level=41, total_calories=900),
    )
    summary_provider = telegram_bot._DailySummaryProvider(FakeBridge())
    summary = asyncio.run(summary_provider.get_daily_summary("u1"))
    assert summary["workout"] == "Morning Run"
    assert summary["active_calories"] == 900
    assert summary["steps"] == 12345
    assert summary["stress_avg"] == 41

    tomorrow_provider = telegram_bot._TomorrowPlanProvider(
        FakeBridge(),
        SimpleNamespace(_load=lambda user_id: object()),
        telegram_bot._MorningPlanStateStore(Path("/tmp/test_morning_state_unused")),
    )
    tomorrow_plan = asyncio.run(tomorrow_provider.get_tomorrow_plan("u1"))
    assert tomorrow_plan["session"] == "Tempo Run"
    assert tomorrow_plan["recommended_bedtime"] == "22:00"


def test_workout_photo_analysis_depends_on_photo_bytes(monkeypatch):
    import garmin_coach.telegram_bot as telegram_bot
    from garmin_coach.models.coaching import WorkoutAnalysis

    class FakeBridge:
        def latest_activity_payload(self, user_id):
            return {"activity_id": "a1", "type": "run"}

        async def create_workout_analysis(self, user_id, activity):
            return WorkoutAnalysis(
                summary="분석", comparison_to_recent="base", coaching_notes=["note"]
            )

    class FakeFoodAnalyzer:
        async def analyze(self, user_id, photo):
            return {}

    router = telegram_bot._PhotoRouter(FakeBridge(), FakeFoodAnalyzer())
    png = asyncio.run(router.analyze_workout("u1", b"\x89PNGdemo"))
    jpeg = asyncio.run(router.analyze_workout("u1", b"\xff\xd8\xffdemo"))
    assert png["comparison_to_recent"] != jpeg["comparison_to_recent"]
    assert "Garmin 활동 기록" in png["comparison_to_recent"]


def test_workout_photo_analysis_uses_user_scoped_latest_activity():
    import garmin_coach.telegram_bot as telegram_bot
    from garmin_coach.models.coaching import WorkoutAnalysis

    class FakeBridge:
        def latest_activity_payload(self, user_id):
            return {"activity_id": f"{user_id}-activity", "type": "run"}

        async def create_workout_analysis(self, user_id, activity):
            return WorkoutAnalysis(
                summary=activity["activity_id"],
                comparison_to_recent="base",
                coaching_notes=["note"],
            )

    class FakeFoodAnalyzer2:
        async def analyze(self, user_id, photo):
            return {}

    router = telegram_bot._PhotoRouter(FakeBridge(), FakeFoodAnalyzer2())
    result = asyncio.run(router.analyze_workout("user-a", b"\x89PNGdemo"))
    assert result["summary"] == "user-a-activity"


def test_runtime_report_uses_user_scoped_database_data():
    import garmin_coach.telegram_bot as telegram_bot
    from garmin_coach.storage.database import GarminCoachDatabase
    from garmin_coach.models.health_metrics import TrainingLoad
    from garmin_coach.models.coaching import WeeklyPlan

    db = GarminCoachDatabase(":memory:")
    # The report covers the last 30 days, so the fixture date must be recent.
    recent_ts = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%dT10:00:00")
    db.save_activity(
        "u1",
        "a1",
        recent_ts,
        {
            "activity_id": "a1",
            "start_time": recent_ts,
            "distance_km": 10.0,
            "duration_min": 50.0,
        },
    )
    db.save_activity(
        "u2",
        "a2",
        recent_ts,
        {
            "activity_id": "a2",
            "start_time": recent_ts,
            "distance_km": 42.0,
            "duration_min": 180.0,
        },
    )

    class FakeProfileService:
        def _load(self, user_id):
            return None

    class FakeBridge(telegram_bot._RuntimeDataBridge):
        def __init__(self):
            super().__init__(FakeProfileService(), db)

        def build_health_metrics(self, user_id, target_date=None):
            from datetime import date
            from garmin_coach.models import HealthMetrics

            return HealthMetrics(
                metric_date=target_date or date.today(),
                training_load=TrainingLoad(ctl=1, atl=2, tsb=3, ramp_rate=4),
            )

        async def create_weekly_plan(self, user_id):
            return WeeklyPlan(notes=[f"plan-{user_id}"])

    report = asyncio.run(FakeBridge().create_report("u1", 30, "최근 30일"))
    assert report.summary.sessions == 1
    assert report.summary.total_distance_km == 10.0
    assert report.coach_comment == "plan-u1"


def test_build_telegram_application_uses_stream2_runtime(monkeypatch):
    import garmin_coach.telegram_bot as telegram_bot
    from garmin_coach.interfaces.telegram import adapter as adapter_module
    from garmin_coach.interfaces.telegram import handlers as handlers_module

    telegram, telegram_ext = _fake_telegram_modules()
    fake_app = FakeApplication()

    class FakeBuilder:
        def token(self, token):
            self.token_value = token
            return self

        def build(self):
            return fake_app

    fake_application_cls = SimpleNamespace(builder=lambda: FakeBuilder())
    telegram_ext = SimpleNamespace(**telegram_ext.__dict__, Application=fake_application_cls)

    monkeypatch.setattr(telegram_bot, "TELEGRAM_AVAILABLE", True)
    monkeypatch.setattr(telegram_bot, "_load_telegram_modules", lambda: (telegram, telegram_ext))
    monkeypatch.setattr(adapter_module, "_load_telegram", lambda: (telegram, telegram_ext))
    monkeypatch.setattr(handlers_module, "_load_telegram", lambda: (telegram, telegram_ext))

    class FakeRegistry:
        async def register_user(self, user_id):
            return None

        async def get_all_user_ids(self):
            return ["42"]

    monkeypatch.setattr(telegram_bot, "TelegramUserRegistry", FakeRegistry)

    class FakeProfileService:
        async def has_profile(self, user_id):
            return False

        async def summarize_profile(self, user_id):
            return "summary"

        async def create_profile(self, user_id, payload):
            return "created"

        async def update_profile_sections(self, user_id, payload):
            return None

        async def load_progress(self, user_id):
            return {}

        async def save_progress(self, user_id, payload):
            return None

        async def clear_progress(self, user_id):
            return None

        async def summarize_settings(self, user_id):
            return "settings"

        async def update_profile_name(self, user_id, value):
            return None

        async def update_weight(self, user_id, value):
            return None

        async def update_available_days(self, user_id, value):
            return None

        async def update_schedule(self, user_id, field, value):
            return None

        async def update_nutrition(self, user_id, weight_goal, dietary_style):
            return None

        async def update_medical(self, user_id, beta_blocker, current_injuries, notes):
            return None

        async def update_sleep(self, user_id, bedtime, wake_time, issues):
            return None

        async def update_preferences(
            self,
            user_id,
            preferred_training_time,
            cross_training_preferences,
            notification_frequency,
            units,
            timezone,
            strava_connected,
        ):
            return None

        async def update_ai_tone(self, user_id, tone):
            return None

        async def summarize_goals(self, user_id):
            return "goals"

        async def update_goal_event(self, user_id, value):
            return None

        async def update_goal_date(self, user_id, value):
            return None

        async def update_fitness_level(self, user_id, value):
            return None

        async def update_max_weekly_hours(self, user_id, value):
            return None

        async def get_schedule_config(self, user_id):
            return {"morning_time": "07:00", "evening_time": "21:00"}

    monkeypatch.setattr(telegram_bot, "_UserProfileService", lambda: FakeProfileService())

    calls = []

    class FakePostWorkout:
        async def execute(self, user_id, activity):
            calls.append((user_id, activity))

    class FakeMorning:
        async def execute(self, user_id):
            return None

    class FakeNutrition:
        async def execute(self, user_id):
            return None

        async def execute_daily_guide(self, user_id):
            return None

    class FakeNoop:
        async def execute(self, user_id):
            return None

    monkeypatch.setattr(
        telegram_bot,
        "_build_flow_registry",
        lambda adapter, bridge, database: SimpleNamespace(
            morning_briefing=FakeMorning(),
            post_workout=FakePostWorkout(),
            evening_checkin=FakeNoop(),
            nutrition_log=FakeNutrition(),
            injury_report=FakeNoop(),
            onboarding=FakeNoop(),
            settings=FakeNoop(),
            goals=FakeNoop(),
        ),
    )

    sync_bus = telegram_bot.SyncEventBus()
    app = telegram_bot.build_telegram_application(
        token="token-1",
        runtime_config=telegram_bot.TelegramRuntimeConfig(),
        sync_bus=sync_bus,
    )

    registered_commands = sorted(
        handler.command for handler in app.handlers if hasattr(handler, "command")
    )
    assert registered_commands == sorted(
        [
            "start",
            "today",
            "week",
            "report",
            "feedback",
            "nutrition",
            "settings",
            "goals",
            "injury",
            "help",
        ]
    )
    assert "stream2_adapter" in app.bot_data
    assert "stream2_handlers" in app.bot_data
    assert "stream2_scheduler" in app.bot_data
    assert "stream2_sync_bus" in app.bot_data

    from garmin_coach.models import ActivitySummary
    from garmin_coach.models.events import NewActivityEvent, SyncEventType

    sync_bus.emit(
        SyncEventType.NEW_ACTIVITY,
        NewActivityEvent(
            user_id="42",
            activity=ActivitySummary(activity_id="evt-1", type="run"),
        ),
    )
    assert len(app.created_coroutines) == 1
    asyncio.run(app.created_coroutines[0])
    assert calls[0][0] == "42"
    assert calls[0][1]["activity_id"] == "evt-1"
    assert calls[0][1]["type"] == "run"

    assert app.post_init is not None
    asyncio.run(app.post_init(app))
    assert [cmd.command for cmd in app.bot.commands] == [
        "start",
        "today",
        "week",
        "report",
        "feedback",
        "nutrition",
        "settings",
        "goals",
        "injury",
        "help",
    ]
    job_names = [job.name for job in app.job_queue.jobs]
    assert "activity_sync" in job_names
    assert "morning_42" in job_names
    assert "evening_42" in job_names
    assert "weekly_42" in job_names
    assert "monthly_42" in job_names


def test_activity_sync_job_dispatches_for_registered_users(monkeypatch):
    import garmin_coach.telegram_bot as telegram_bot
    from garmin_coach.interfaces.telegram import adapter as adapter_module
    from garmin_coach.interfaces.telegram import handlers as handlers_module

    telegram, telegram_ext = _fake_telegram_modules()
    fake_app = FakeApplication()

    class FakeBuilder:
        def token(self, token):
            return self

        def build(self):
            return fake_app

    fake_application_cls = SimpleNamespace(builder=lambda: FakeBuilder())
    telegram_ext = SimpleNamespace(**telegram_ext.__dict__, Application=fake_application_cls)

    monkeypatch.setattr(telegram_bot, "TELEGRAM_AVAILABLE", True)
    monkeypatch.setattr(telegram_bot, "_load_telegram_modules", lambda: (telegram, telegram_ext))
    monkeypatch.setattr(adapter_module, "_load_telegram", lambda: (telegram, telegram_ext))
    monkeypatch.setattr(handlers_module, "_load_telegram", lambda: (telegram, telegram_ext))

    class FakeRegistry:
        async def register_user(self, user_id):
            return None

        async def get_all_user_ids(self):
            return ["u1", "u2"]

    dispatched = []

    class FakeSyncService:
        def __init__(self, adapter, database, bus, user_id):
            self.user_id = user_id

        def sync_recent_activities(self):
            dispatched.append(self.user_id)

        def sync_daily_health(self):
            return None

    monkeypatch.setattr(telegram_bot, "TelegramUserRegistry", FakeRegistry)
    monkeypatch.setattr(telegram_bot, "GarminSyncService", FakeSyncService)

    app = telegram_bot.build_telegram_application(
        token="token-1", runtime_config=telegram_bot.TelegramRuntimeConfig()
    )
    sync_job = next(job for job in app.job_queue.jobs if job.name == "activity_sync")
    asyncio.run(sync_job.callback(SimpleNamespace(job=sync_job, application=app)))
    assert dispatched == ["u1", "u2"]


def test_postworkout_callbacks_are_live(monkeypatch):
    import garmin_coach.interfaces.telegram.handlers as handlers_module

    telegram, telegram_ext = _fake_telegram_modules()
    monkeypatch.setattr(handlers_module, "_load_telegram", lambda: (telegram, telegram_ext))

    adapter = handlers_module.TelegramAdapter(FakeBot())
    sent = []

    async def fake_send(user_id, text, buttons=None):
        sent.append(text)

    adapter.send_message = fake_send
    handlers = handlers_module.TelegramHandlers(adapter, flows=None)

    class FakeQuery:
        def __init__(self, data):
            self.data = data

        async def answer(self):
            return None

    update_ate = SimpleNamespace(
        effective_user=SimpleNamespace(id=42), callback_query=FakeQuery("postworkout:ate")
    )
    update_later = SimpleNamespace(
        effective_user=SimpleNamespace(id=42), callback_query=FakeQuery("postworkout:later")
    )
    asyncio.run(handlers._on_callback(update_ate, None))
    asyncio.run(handlers._on_callback(update_later, None))
    assert any("회복 영양" in text for text in sent)
    assert any("30분" in text for text in sent)


def test_unknown_photo_timeout_does_not_emit_fake_success(monkeypatch):
    import garmin_coach.interfaces.telegram.handlers as handlers_module
    from garmin_coach.ports import InputAborted, InputAbortReason, InputType

    telegram, telegram_ext = _fake_telegram_modules()
    monkeypatch.setattr(handlers_module, "_load_telegram", lambda: (telegram, telegram_ext))

    adapter = handlers_module.TelegramAdapter(FakeBot())
    sent = []

    async def fake_send(user_id, text, buttons=None):
        sent.append(text)

    async def fake_request_select(user_id, prompt, options):
        raise InputAborted(InputType.SELECT, InputAbortReason.TIMEOUT)

    adapter.send_message = fake_send
    adapter.request_select = fake_request_select

    class FakePhotoRouter:
        async def auto_detect_type(self, photo):
            return None

        async def analyze_workout(self, user_id, photo):
            return {}

        async def analyze_food(self, user_id, photo):
            return {}

    handlers = handlers_module.TelegramHandlers(adapter, flows=None, photo_router=FakePhotoRouter())

    class FakeFile:
        async def download_as_bytearray(self):
            return bytearray(b"raw")

    class FakePhoto:
        async def get_file(self):
            return FakeFile()

    update = SimpleNamespace(
        effective_user=SimpleNamespace(id=42),
        message=SimpleNamespace(photo=[FakePhoto()]),
    )
    asyncio.run(handlers._on_photo(update, None))
    assert any("시간이 초과" in text for text in sent)
    assert not any("사진이 저장되었습니다" in text for text in sent)


def test_unknown_photo_classification_shares_user_lock(monkeypatch):
    import garmin_coach.interfaces.telegram.handlers as handlers_module

    telegram, telegram_ext = _fake_telegram_modules()
    monkeypatch.setattr(handlers_module, "_load_telegram", lambda: (telegram, telegram_ext))

    adapter = handlers_module.TelegramAdapter(FakeBot())
    overlap = {"active": False, "saw": False}

    async def fake_request_select(user_id, prompt, options):
        if overlap["active"]:
            overlap["saw"] = True
        overlap["active"] = True
        await asyncio.sleep(0.01)
        overlap["active"] = False
        return "photo_type:other"

    async def fake_send(user_id, text, buttons=None):
        return None

    adapter.request_select = fake_request_select
    adapter.send_message = fake_send

    class FakeMorning:
        async def execute(self, user_id):
            if overlap["active"]:
                overlap["saw"] = True
            overlap["active"] = True
            await asyncio.sleep(0.01)
            overlap["active"] = False

    class FakeFlows:
        def __init__(self):
            self.morning_briefing = FakeMorning()
            self.post_workout = None
            self.evening_checkin = None
            self.nutrition_log = None
            self.injury_report = None
            self.onboarding = None
            self.settings = None
            self.goals = None

    class FakePhotoRouter:
        async def auto_detect_type(self, photo):
            return None

        async def analyze_workout(self, user_id, photo):
            return {}

        async def analyze_food(self, user_id, photo):
            return {}

    fake_flows = FakeFlows()

    handlers = handlers_module.TelegramHandlers(
        adapter,
        flows=fake_flows,
        photo_router=FakePhotoRouter(),
    )

    class FakeFile:
        async def download_as_bytearray(self):
            return bytearray(b"raw")

    class FakePhoto:
        async def get_file(self):
            return FakeFile()

    update = SimpleNamespace(
        effective_user=SimpleNamespace(id=42),
        message=SimpleNamespace(photo=[FakePhoto()]),
    )

    async def run_both():
        await asyncio.gather(
            handlers._on_photo(update, None),
            handlers._run_locked("42", lambda: fake_flows.morning_briefing.execute("42")),
        )

    asyncio.run(run_both())
    assert overlap["saw"] is False
