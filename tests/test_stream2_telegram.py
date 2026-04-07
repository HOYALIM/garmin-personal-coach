import asyncio
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

    async def send_message(self, chat_id, text, reply_markup=None):
        self.messages.append({"chat_id": chat_id, "text": text, "reply_markup": reply_markup})

    async def send_photo(self, chat_id, photo, caption=None):
        self.photos.append({"chat_id": chat_id, "photo": photo, "caption": caption})

    async def set_my_commands(self, commands):
        self.commands = commands


class FakeJob:
    def __init__(self, name=None, data=None):
        self.name = name
        self.data = data
        self.removed = False

    def schedule_removal(self):
        self.removed = True


class FakeJobQueue:
    def __init__(self):
        self.jobs = []

    def run_daily(self, callback, time, name, days=None, data=None):
        self.jobs.append(FakeJob(name=name, data=data))

    def run_monthly(self, callback, when, day, name):
        self.jobs.append(FakeJob(name=name))

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
    assert calls == [
        ("11", {"activity_id": "abc", "type": "run", "duration_min": 42, "avg_hr": 150})
    ]


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
    monkeypatch.setattr(telegram_bot, "load_config", lambda: {"schedule": {}})

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
        lambda adapter: SimpleNamespace(
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
