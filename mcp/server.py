"""MCP server for Garmin Personal Coach using JSON-RPC over stdio."""

import json
import sys
from typing import Any

from garmin_coach._version import __version__
from garmin_coach.training_load_manager import get_training_load_manager


def get_training_status() -> dict:
    try:
        manager = get_training_load_manager()
        context = manager.get_context()
        return {
            "status": "success",
            "data": context,
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}


def get_user_profile() -> dict:
    try:
        from garmin_coach.wizard import load_config

        config = load_config()
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
        return {"status": "error", "message": str(e)}


def get_recent_activities(days: int = 7) -> dict:
    try:
        manager = get_training_load_manager()
        calc = manager.calculator

        from datetime import date, timedelta

        activities = []
        for i in range(days):
            d = date.today() - timedelta(days=i)
            daily_load = calc.get_daily_load(d)
            if daily_load:
                activities.append(
                    {
                        "date": d.isoformat(),
                        "trimp": daily_load.trimp,
                        "sport": daily_load.sport.value,
                        "duration_min": daily_load.duration_min,
                        "description": daily_load.description,
                    }
                )

        return {
            "status": "success",
            "data": activities,
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}


def handle_natural_language(message: str) -> dict:
    try:
        from garmin_coach.handler import process_message

        response = process_message(message)
        return {
            "status": "success",
            "response": response,
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}


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
        return {"status": "error", "message": str(e)}


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
    "get_training_plan": get_training_plan,
}


def handle_tool_call(name: str, arguments: dict) -> dict:
    if name not in TOOL_HANDLERS:
        return {"status": "error", "message": f"Unknown tool: {name}"}

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

            elif method == "notifications/initialized":
                pass

        except json.JSONDecodeError:
            send_error(None, -32700, "Parse error")
        except Exception as e:
            send_error(request_id if "request_id" in locals() else None, -32603, str(e))


if __name__ == "__main__":
    main()
