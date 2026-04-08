import asyncio
from datetime import date, timedelta
from pathlib import Path


def test_onboarding_phase1_timeout_keeps_profile_and_resume_step():
    from garmin_coach.flows.onboarding import OnboardingFlow
    from garmin_coach.ports import CoachingPort, InputAbortReason, InputAborted, InputType

    class FakeService:
        def __init__(self):
            self.profile_exists = False
            self.progress = {}
            self.created_payloads = []
            self.updated_sections = []
            self.cleared = False

        async def has_profile(self, user_id):
            return self.profile_exists

        async def summarize_profile(self, user_id):
            return "summary"

        async def connect_garmin(self, user_id, email, password):
            return True

        async def create_profile(self, user_id, payload):
            self.created_payloads.append(dict(payload))
            self.profile_exists = True
            return "created"

        async def update_profile_sections(self, user_id, payload):
            self.updated_sections.append(payload)

        async def load_progress(self, user_id):
            return dict(self.progress)

        async def save_progress(self, user_id, payload):
            self.progress = dict(payload)

        async def clear_progress(self, user_id):
            self.cleared = True

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
            if "이메일" in prompt:
                return "runner@example.com"
            if "비밀번호" in prompt:
                return "pw"
            if "이름" in prompt:
                return "Runner"
            if "목표 대회" in prompt:
                return "Seoul Marathon"
            if "아침 브리핑" in prompt:
                return "06:15"
            if "저녁 체크인" in prompt:
                return "21:45"
            if "알레르기" in prompt:
                raise InputAborted(InputType.TEXT, InputAbortReason.TIMEOUT)
            raise AssertionError(prompt)

        async def request_number(self, user_id, prompt, min_val=None, max_val=None):
            if "나이" in prompt:
                return 31
            if "키" in prompt:
                return 175
            if "체중" in prompt:
                return 68
            if "주당 훈련 가능" in prompt:
                return 5
            raise AssertionError(prompt)

        async def request_date(self, user_id, prompt):
            return date.today() + timedelta(days=30)

        async def request_select(self, user_id, prompt, options):
            if "목표 날짜가 있나요" in prompt:
                return "yes"
            if "성별" in prompt:
                return "male"
            if "현재 운동 수준" in prompt:
                return "intermediate"
            if "추가 건강/영양/수면 설정" in prompt:
                return "continue"
            raise AssertionError(prompt)

        async def request_multi_select(self, user_id, prompt, options):
            if "주로 하는 운동" in prompt:
                return ["running"]
            raise AssertionError(prompt)

        async def request_photo(self, user_id, prompt):
            return None

    service = FakeService()
    port = FakePort()
    asyncio.run(OnboardingFlow(port, service).execute("u1"))
    assert len(service.created_payloads) == 1
    assert service.updated_sections == []
    assert service.cleared is False
    assert service.progress["profile_created"] is True
    assert service.progress["status"] == "timeout"
    assert service.progress["current_step"] == "phase2.allergies"
    assert any("Phase 1" in message for message in port.messages)


def test_onboarding_resume_phase2_without_duplicate_phase1_questions():
    from garmin_coach.flows.onboarding import OnboardingFlow
    from garmin_coach.ports import CoachingPort

    class FakeService:
        def __init__(self):
            self.progress = {
                "schema_version": 2,
                "status": "timeout",
                "current_step": "phase2.allergies",
                "profile_created": True,
                "phase1": {
                    "garmin_email": "runner@example.com",
                    "garmin_connected": True,
                    "name": "Runner",
                    "age": 31,
                    "sex": "male",
                    "height_cm": 175,
                    "weight_kg": 68,
                    "sports": ["running"],
                    "target_event": "Seoul Marathon",
                    "has_goal_date": "yes",
                    "goal_date": (date.today() + timedelta(days=30)).isoformat(),
                    "fitness_level": "intermediate",
                    "available_days": 5,
                    "morning_time": "06:15",
                    "evening_time": "21:45",
                },
                "phase2": {},
                "phase3": {},
                "phase2_status": "in_progress",
                "phase3_status": "pending",
            }
            self.updated_sections = []
            self.cleared = False

        async def has_profile(self, user_id):
            return True

        async def summarize_profile(self, user_id):
            return "summary"

        async def connect_garmin(self, user_id, email, password):
            raise AssertionError("Garmin auth should not repeat")

        async def create_profile(self, user_id, payload):
            raise AssertionError("Profile should not be recreated")

        async def update_profile_sections(self, user_id, payload):
            self.updated_sections.append(payload)

        async def load_progress(self, user_id):
            return dict(self.progress)

        async def save_progress(self, user_id, payload):
            self.progress = dict(payload)

        async def clear_progress(self, user_id):
            self.cleared = True

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
            if any(
                token in prompt
                for token in ["이메일", "이름", "목표 대회", "아침 브리핑", "저녁 체크인"]
            ):
                raise AssertionError(f"prompt repeated unexpectedly: {prompt}")
            if "알레르기" in prompt:
                return "peanut"
            if "식이 제한" in prompt:
                return "lactose"
            if "통증이나 부상" in prompt:
                return "knee"
            if "건강 메모" in prompt:
                return "없음"
            if "취침" in prompt:
                return "23:00"
            if "기상" in prompt:
                return "07:00"
            if "수면 관련 이슈" in prompt:
                return "없음"
            if "시간대" in prompt:
                return "Asia/Seoul"
            raise AssertionError(prompt)

        async def request_number(self, user_id, prompt, min_val=None, max_val=None):
            raise AssertionError(prompt)

        async def request_date(self, user_id, prompt):
            raise AssertionError(prompt)

        async def request_select(self, user_id, prompt, options):
            if "베타차단제" in prompt:
                return "yes"
            if "마지막으로 코칭 선호 설정" in prompt:
                return "skip"
            raise AssertionError(prompt)

        async def request_multi_select(self, user_id, prompt, options):
            raise AssertionError(prompt)

        async def request_photo(self, user_id, prompt):
            return None

    service = FakeService()
    port = FakePort()
    asyncio.run(OnboardingFlow(port, service).execute("u1"))
    assert service.updated_sections
    assert service.updated_sections[0]["medical"]["current_injuries"] == ["knee"]
    assert service.updated_sections[0]["nutrition"]["allergies"] == ["peanut"]
    assert service.cleared is True
    assert any("이어" in message for message in port.messages)


def test_onboarding_failed_garmin_auth_does_not_create_profile_or_store_abort_as_business_value():
    from garmin_coach.flows.onboarding import OnboardingFlow
    from garmin_coach.ports import CoachingPort

    class FakeService:
        def __init__(self):
            self.progress = {}
            self.create_called = False

        async def has_profile(self, user_id):
            return False

        async def summarize_profile(self, user_id):
            return "summary"

        async def connect_garmin(self, user_id, email, password):
            return False

        async def create_profile(self, user_id, payload):
            self.create_called = True
            return "created"

        async def update_profile_sections(self, user_id, payload):
            return None

        async def load_progress(self, user_id):
            return dict(self.progress)

        async def save_progress(self, user_id, payload):
            self.progress = dict(payload)

        async def clear_progress(self, user_id):
            return None

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
            if "이메일" in prompt:
                return "runner@example.com"
            if "비밀번호" in prompt:
                return "pw"
            raise AssertionError(prompt)

        async def request_number(self, user_id, prompt, min_val=None, max_val=None):
            raise AssertionError(prompt)

        async def request_date(self, user_id, prompt):
            raise AssertionError(prompt)

        async def request_select(self, user_id, prompt, options):
            if "다시 시도할까요" in prompt:
                return "later"
            raise AssertionError(prompt)

        async def request_multi_select(self, user_id, prompt, options):
            raise AssertionError(prompt)

        async def request_photo(self, user_id, prompt):
            return None

    service = FakeService()
    port = FakePort()
    asyncio.run(OnboardingFlow(port, service).execute("u1"))
    assert service.create_called is False
    assert service.progress["status"] == "cancelled"
    assert service.progress["current_step"] == "phase1.garmin_auth"
    assert service.progress["phase1"]["garmin_email"] == "runner@example.com"
    assert "cancelled" not in str(service.progress["phase1"])
    assert any("중단" in message for message in port.messages)


def test_settings_side_effect_runs_once_only_after_successful_save(tmp_path):
    import garmin_coach.telegram_bot as telegram_bot
    from garmin_coach.profile_manager import ProfileManager

    class TestService(telegram_bot._UserProfileService):
        def _manager(self, user_id):
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
    calls = []

    async def callback(user_id, change_kind, profile):
        calls.append((user_id, change_kind, profile.schedule.morning_checkin["time"]))

    service.set_settings_side_effect(callback)
    asyncio.run(service.update_schedule("u1", "morning", "07:30"))
    assert calls == [("u1", "schedule", "07:30")]
    assert service._load("u1").schedule.morning_checkin["time"] == "07:30"

    class FailingService(TestService):
        def _save(self, user_id, profile):
            raise RuntimeError("save failed")

    failing = FailingService()
    failing.set_settings_side_effect(callback)
    try:
        asyncio.run(failing.update_schedule("u1", "morning", "08:00"))
    except RuntimeError:
        pass
    assert calls == [("u1", "schedule", "07:30")]


def test_safe_profile_serialization_redacts_stream3_sensitive_fields():
    from garmin_coach.models import (
        FitnessLevel,
        GarminAuth,
        InjuryRecord,
        MedicalProfile,
        NutritionProfile,
        TrainingGoal,
        UserProfile,
    )

    profile = UserProfile(
        garmin_credentials=GarminAuth(email="runner@example.com", connected=True),
        birth_date=date.today() - timedelta(days=30 * 365),
        sex="male",
        height_cm=175,
        weight_kg=70,
        goal=TrainingGoal(type="marathon", weekly_volume_km=60),
        fitness_level=FitnessLevel(level="advanced"),
        medical=MedicalProfile(
            beta_blocker=True,
            notes="cardiac note",
            current_injuries=[InjuryRecord(body_part="knee", description="pain")],
        ),
        nutrition=NutritionProfile(allergies=["peanut"], supplements=["iron"]),
    )
    payload = profile.to_safe_dict()
    assert payload["garmin_credentials"]["email"].startswith("r***@")
    assert "cardiac note" not in str(payload)
    assert "peanut" not in str(payload)
    assert "iron" not in str(payload)


def test_flows_and_wizard_remain_telegram_free():
    root = Path("/Users/ho/code/garmin-personal-coach/garmin_coach")
    for directory in (root / "flows", root / "wizard"):
        for path in directory.glob("*.py"):
            imports = [
                line.strip()
                for line in path.read_text().splitlines()
                if line.strip().startswith(("import ", "from "))
            ]
            joined = "\n".join(imports)
            assert "from telegram import" not in joined
            assert "import telegram" not in joined
