from enum import Enum
from typing import Callable


class Locale(str, Enum):
    KO = "ko"
    EN = "en"
    ZH = "zh"


DEFAULT_LOCALE = Locale.EN


class I18n:
    def __init__(self, locale: Locale = DEFAULT_LOCALE):
        self.locale = locale

    def t(self, key: str) -> str:
        return _translations.get(self.locale, {}).get(key, key)


_translations: dict[Locale, dict[str, str]] = {
    Locale.KO: {
        "start.welcome": "안녕하세요, {name}! 🏃\n\n당신의 퍼스널 코치입니다!\n\n도움말: /help\n컨디션: /status\n일정: /plan\n운동 기록: /log",
        "help.text": "📚 사용 가능한 명령어:\n\n/start - 시작\n/help - 도움말\n/status - 오늘 컨디션 확인\n/plan - 오늘의 훈련 일정\n/log - 운동 기록하기\n/profile - 내 프로필\n/setup - 설정\n\n💬 또는 그냥 메시지를 보내세요!\n예: '오늘 컨디션 어때?' '운동 끝' '피곤해'",
        "profile.title": "📋 내 프로필",
        "profile.name": "이름",
        "profile.age": "나이",
        "profile.sports": "종목",
        "profile.fitness": "피트니스",
        "profile.not_set": "설정되지 않음",
        "profile.years": "세",
        "setup.prompt": "⚙️ 설정은 터미널에서 진행해주세요:\n\npip install garmin-personal-coach\ngarmin-coach setup\n\n설정이 완료되면 다시 /start 을 눌러주세요.",
        "log.workout_type": "🏃 어떤 운동을 했나요?\n\n예: 런닝, 사이클링, 수영, 웨이트 등",
        "log.duration": "✅ {type} - 몇 분 했나요?",
        "log.feeling": "✅ {duration}분 - 컨디션은 어때요? (1-5)",
        "log.complete": "✅ 기록 완료!",
        "log.complete_with_response": "✅ 기록 완료!\n\n{response}",
        "cancel": "취소했어요. 다른 명령어를 입력해주세요.",
        "error.status": "죄송합니다. 데이터를 불러오는데 문제가 발생했어요.",
        "error.plan": "죄송합니다. 일정을 불러오는데 문제가 발생했어요.",
        "error.profile": "프로필을 불러오는데 문제가 발생했어요.",
        "error.generic": "죄송합니다. 일시적인 문제가 발생했어요. 다시 시도해주세요.",
    },
    Locale.EN: {
        "start.welcome": "Hi {name}! 🏃\n\nI'm your personal coach!\n\nHelp: /help\nStatus: /status\nPlan: /plan\nLog workout: /log",
        "help.text": "📚 Available commands:\n\n/start - Start\n/help - Help\n/status - Check today's status\n/plan - Today's training plan\n/log - Log workout\n/profile - My profile\n/setup - Settings\n\n💬 Or just send a message!\nExample: 'How am I doing?' 'Workout done' 'I'm tired'",
        "profile.title": "📋 My Profile",
        "profile.name": "Name",
        "profile.age": "Age",
        "profile.sports": "Sports",
        "profile.fitness": "Fitness",
        "profile.not_set": "Not set",
        "profile.years": "years",
        "setup.prompt": "⚙️ Settings are done in terminal:\n\npip install garmin-personal-coach\ngarmin-coach setup\n\nOnce done, press /start again.",
        "log.workout_type": "🏃 What workout did you do?\n\nExample: Running, Cycling, Swimming, Weights",
        "log.duration": "✅ {type} - How many minutes?",
        "log.feeling": "✅ {duration} min - How do you feel? (1-5)",
        "log.complete": "✅ Log complete!",
        "log.complete_with_response": "✅ Log complete!\n\n{response}",
        "cancel": "Cancelled. Enter another command.",
        "error.status": "Sorry, there was a problem loading data.",
        "error.plan": "Sorry, there was a problem loading your plan.",
        "error.profile": "Sorry, there was a problem loading your profile.",
        "error.generic": "Sorry, a temporary error occurred. Please try again.",
    },
    Locale.ZH: {
        "start.welcome": "你好，{name}！🏃\n\n我是你的私人教练！\n\n帮助：/help\n状态：/status\n计划：/plan\n记录：/log",
        "help.text": "📚 可用命令：\n\n/start - 开始\n/help - 帮助\n/status - 查看今日状态\n/plan - 今日训练计划\n/log - 记录训练\n/profile - 我的资料\n/setup - 设置\n\n💬 或者直接发消息！\n例如：'今天状态怎么样？' '训练完了' '累了'",
        "profile.title": "📋 我的资料",
        "profile.name": "姓名",
        "profile.age": "年龄",
        "profile.sports": "运动项目",
        "profile.fitness": "健身水平",
        "profile.not_set": "未设置",
        "profile.years": "岁",
        "setup.prompt": "⚙️ 请在终端进行设置：\n\npip install garmin-personal-coach\ngarmin-coach setup\n\n设置完成后，请按 /start 再次开始。",
        "log.workout_type": "🏃 你做了什么运动？\n\n例如：跑步、骑行、游泳、力量训练",
        "log.duration": "✅ {type} - 做了多少分钟？",
        "log.feeling": "✅ {duration}分钟 - 感觉如何？(1-5)",
        "log.complete": "✅ 记录完成！",
        "log.complete_with_response": "✅ 记录完成！\n\n{response}",
        "cancel": "已取消。请输入其他命令。",
        "error.status": "抱歉，加载数据时出现问题。",
        "error.plan": "抱歉，加载计划时出现问题。",
        "error.profile": "抱歉，加载资料时出现问题。",
        "error.generic": "抱歉，发生临时错误。请重试。",
    },
}


def get_i18n(locale: Locale = None) -> I18n:
    return I18n(locale or DEFAULT_LOCALE)


def detect_locale(text: str) -> Locale:
    """Simple locale detection based on text content."""
    if any(ord(c) >= 0xAC00 for c in text):
        return Locale.KO
    if any(ord(c) >= 0x4E00 and ord(c) <= 0x9FFF for c in text):
        return Locale.ZH
    return Locale.EN
