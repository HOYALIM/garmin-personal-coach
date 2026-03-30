import json
import sys
from pathlib import Path
from typing import Any

from garmin_coach._version import __version__

# Extend import path to access garmin_coach package from repo root
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from garmin_coach.logging_config import log_info, log_error
from garmin_coach.training_load_manager import get_training_load_manager
from garmin_coach.rate_limit import MCP_LIMITER


# JSON-RPC standard error codes
ERROR_PARSE_ERROR = -32700
ERROR_INVALID_REQUEST = -32600
ERROR_METHOD_NOT_FOUND = -32601
ERROR_INVALID_PARAMS = -32602
ERROR_INTERNAL_ERROR = -32603

# Application-specific error codes (1000-1999)
ERROR_TRAINING_LOAD = 1001
ERROR_PROFILE_NOT_FOUND = 1002
ERROR_GARMIN_NOT_CONNECTED = 1003
ERROR_AI_NOT_CONFIGURED = 1004
ERROR_VALIDATION_FAILED = 1005
ERROR_RATE_LIMITED = 1006


class CoachError(Exception):
    code: int = ERROR_INTERNAL_ERROR
    message: str = "Internal error"

    def to_dict(self) -> dict:
        return {
            "code": self.code,
            "message": self.message,
            "data": getattr(self, "data", None),
        }


class TrainingLoadError(CoachError):
    code = ERROR_TRAINING_LOAD
    message = "Training load data unavailable"


class ProfileNotFoundError(CoachError):
    code = ERROR_PROFILE_NOT_FOUND
    message = "User profile not found"


class GarminNotConnectedError(CoachError):
    code = ERROR_GARMIN_NOT_CONNECTED
    message = "Garmin account not connected"


class AINotConfiguredError(CoachError):
    code = ERROR_AI_NOT_CONFIGURED
    message = "AI not configured"


class ValidationError(CoachError):
    code = ERROR_VALIDATION_FAILED
    message = "Validation failed"


def get_training_status() -> dict:
    try:
        manager = get_training_load_manager()
        context = manager.get_context()
        return {
            "status": "success",
            "data": context,
        }
    except TrainingLoadError as e:
        return {"status": "error", "code": e.code, "message": e.message}
    except Exception as e:
        return {"status": "error", "code": ERROR_TRAINING_LOAD, "message": str(e)}


def check_garmin_connection() -> bool:
    """Check if Garmin session is available."""
    try:
        from garmin_coach.activity_fetch import resume_garth

        return resume_garth()
    except Exception:
        return False


def check_training_load_manager() -> bool:
    """Check if TrainingLoadManager is available."""
    try:
        from garmin_coach.training_load_manager import TrainingLoadManager

        return True
    except Exception:
        return False


def handle_health(params: dict) -> dict:
    """Handle health check request."""
    garmin_ok = check_garmin_connection()
    tlm_ok = check_training_load_manager()

    status = "healthy" if (garmin_ok and tlm_ok) else "degraded"

    return {
        "status": status,
        "version": __version__,
        "components": {
            "garmin": "ok" if garmin_ok else "unavailable",
            "training_load": "ok" if tlm_ok else "unavailable",
        },
    }


def get_user_profile() -> dict:
    try:
        from garmin_coach.wizard import load_config

        config = load_config()
        if not config:
            return {
                "status": "error",
                "code": ERROR_PROFILE_NOT_FOUND,
                "message": "Run 'garmin-coach setup' first",
            }
        return {
            "status": "success",
            "data": {
                "name": config.get("name", ""),
                "age": config.get("age"),
                "sports": config.get("sports", []),
                "fitness_level": config.get("fitness_level", ""),
                "setup_complete": config.get("setup_complete", False),
            },
        }
    except Exception as e:
        return {"status": "error", "code": ERROR_PROFILE_NOT_FOUND, "message": str(e)}


def get_recent_activities(days: int = 7) -> dict:
    try:
        manager = get_training_load_manager()
        calc = manager.calculator

        from datetime import date, timedelta

        activities = []
        start_date = date.today() - timedelta(days=max(days - 1, 0))
        for daily_load in calc.get_sessions_in_range(start_date, date.today()):
            activities.append(
                {
                    "date": daily_load.date.isoformat(),
                    "trimp": daily_load.trimp,
                    "sport": daily_load.sport.value,
                    "duration_min": daily_load.duration_min,
                    "description": daily_load.description,
                }
            )

        return {
            "status": "success",
            "data": list(reversed(activities)),
        }
    except Exception as e:
        return {"status": "error", "code": ERROR_TRAINING_LOAD, "message": str(e)}


def handle_natural_language(message: str) -> dict:
    try:
        from garmin_coach.handler import process_message

        response = process_message(message)
        return {
            "status": "success",
            "response": response,
        }
    except Exception as e:
        return {"status": "error", "code": ERROR_INTERNAL_ERROR, "message": str(e)}


def get_training_plan() -> dict:
    try:
        manager = get_training_load_manager()
        tsb = manager.get_context().get("tsb", 0)

        if tsb < -25:
            plan = "Rest day - recovery priority"
        elif tsb < -10:
            plan = "Easy day - active recovery"
        elif tsb > 25:
            plan = "High intensity training"
        else:
            plan = "Steady training - Zone 2 focus"

        return {
            "status": "success",
            "data": {
                "recommended_plan": plan,
                "tsb": tsb,
            },
        }
    except Exception as e:
        return {"status": "error", "code": ERROR_TRAINING_LOAD, "message": str(e)}


TOOLS = [
    {
        "name": "get_training_status",
        "description": "Get current training load status (CTL, ATL, TSB)",
        "inputSchema": {
            "type": "object",
            "properties": {},
        },
    },
    {
        "name": "get_user_profile",
        "description": "Get user profile information",
        "inputSchema": {
            "type": "object",
            "properties": {},
        },
    },
    {
        "name": "get_recent_activities",
        "description": "Get recent workout activities",
        "inputSchema": {
            "type": "object",
            "properties": {
                "days": {
                    "type": "number",
                    "description": "Number of days to look back",
                    "default": 7,
                },
            },
        },
    },
    {
        "name": "handle_natural_language",
        "description": "Process natural language message and get coaching response",
        "inputSchema": {
            "type": "object",
            "properties": {
                "message": {
                    "type": "string",
                    "description": "Natural language message (e.g., '오늘 컨디션 어때?', '운동 끝')",
                },
            },
            "required": ["message"],
        },
    },
    {
        "name": "health",
        "description": "Get MCP server health and component status",
        "inputSchema": {
            "type": "object",
            "properties": {},
        },
    },
    {
        "name": "get_training_plan",
        "description": "Get recommended training plan based on current TSB",
        "inputSchema": {
            "type": "object",
            "properties": {},
        },
    },
]


TOOL_HANDLERS = {
    "get_training_status": get_training_status,
    "get_user_profile": get_user_profile,
    "get_recent_activities": get_recent_activities,
    "handle_natural_language": handle_natural_language,
    "health": lambda: handle_health({}),
    "get_training_plan": get_training_plan,
}


def handle_tool_call(name: str, arguments: dict, client_id: str = "default") -> dict:
    if not MCP_LIMITER.is_allowed(client_id):
        remaining = MCP_LIMITER.get_remaining(client_id)
        reset_time = MCP_LIMITER.get_reset_time(client_id)
        return {
            "status": "error",
            "code": ERROR_RATE_LIMITED,
            "message": f"Rate limit exceeded. {remaining} requests remaining. Try again in {int(reset_time)} seconds.",
        }

    if name not in TOOL_HANDLERS:
        return {
            "status": "error",
            "code": ERROR_METHOD_NOT_FOUND,
            "message": f"Unknown tool: {name}",
        }

    handler = TOOL_HANDLERS[name]

    if name in ("get_recent_activities",):
        return handler(arguments.get("days", 7))
    elif name == "handle_natural_language":
        return handler(arguments.get("message", ""))
    else:
        return handler()


def send_response(request_id: Any, result: Any):
    response = {"jsonrpc": "2.0", "id": request_id, "result": result}
    print(json.dumps(response), flush=True)


def send_error(request_id: Any, code: int, message: str):
    response = {"jsonrpc": "2.0", "id": request_id, "error": {"code": code, "message": message}}
    print(json.dumps(response), flush=True)


def main():
    if "--version" in sys.argv:
        print(f"garmin-personal-coach-mcp {__version__}")
        return

    while True:
        try:
            line = sys.stdin.readline()
            if not line:
                break

            request = json.loads(line.strip())

            method = request.get("method")
            request_id = request.get("id")
            params = request.get("params", {})

            if method == "initialize":
                send_response(
                    request_id,
                    {
                        "protocolVersion": "2024-11-05",
                        "capabilities": {"tools": {}},
                        "serverInfo": {
                            "name": "garmin-personal-coach",
                            "version": __version__,
                        },
                    },
                )

            elif method == "tools/list":
                send_response(request_id, {"tools": TOOLS})

            elif method == "tools/call":
                tool_name = params.get("name")
                tool_args = params.get("arguments", {})
                result = handle_tool_call(tool_name, tool_args)
                send_response(
                    request_id,
                    {"content": [{"type": "text", "text": json.dumps(result, ensure_ascii=False)}]},
                )

            elif method == "health":
                res = handle_health(params)
                send_response(request_id, res)

            elif method == "notifications/initialized":
                pass

        except json.JSONDecodeError:
            send_error(None, ERROR_PARSE_ERROR, "Invalid JSON")
        except Exception as e:
            send_error(
                request_id if "request_id" in locals() else None, ERROR_INTERNAL_ERROR, str(e)
            )


if __name__ == "__main__":
    main()
