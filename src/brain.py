"""Appointment-booking voice agent: Claude + tools + per-session memory."""
import json
import boto3

brt = boto3.client("bedrock-runtime", region_name="us-east-1")
MODEL_ID = "us.anthropic.claude-haiku-4-5-20251001-v1:0"

# In-memory availability (Phase 1). Replaced by DynamoDB in Phase 2.
AVAILABILITY = {
    "monday": ["9:00 AM", "11:00 AM", "2:00 PM"],
    "tuesday": ["10:00 AM", "1:00 PM", "4:00 PM"],
    "wednesday": ["9:00 AM", "3:00 PM"],
    "thursday": ["11:00 AM", "2:00 PM", "4:00 PM"],
    "friday": ["10:00 AM", "1:00 PM"],
}
BOOKINGS = {}  # {day: {time: caller_name}}

SYSTEM_PROMPT = (
    "You are a friendly voice receptionist taking appointment bookings over the phone. "
    "Speak naturally and briefly (1-2 sentences), never use lists or markdown. "
    "Collect: the day, a time, and the caller's name. Use your tools to check availability "
    "and to book. Confirm the final booking clearly. If a slot is taken, offer alternatives."
)

TOOLS = [
    {
        "toolSpec": {
            "name": "check_availability",
            "description": "List free appointment slots for a given weekday.",
            "inputSchema": {"json": {
                "type": "object",
                "properties": {"day": {"type": "string", "description": "weekday, lowercase e.g. monday"}},
                "required": ["day"],
            }},
        }
    },
    {
        "toolSpec": {
            "name": "book_appointment",
            "description": "Book a slot for the caller.",
            "inputSchema": {"json": {
                "type": "object",
                "properties": {
                    "day": {"type": "string"},
                    "time": {"type": "string"},
                    "name": {"type": "string"},
                },
                "required": ["day", "time", "name"],
            }},
        }
    },
]


def _run_tool(name, tool_input):
    day = tool_input.get("day", "").lower()
    if name == "check_availability":
        free = [t for t in AVAILABILITY.get(day, []) if t not in BOOKINGS.get(day, {})]
        return {"day": day, "available": free} if free else {"day": day, "available": [], "note": "no slots"}
    if name == "book_appointment":
        time, caller = tool_input["time"], tool_input["name"]
        if time in BOOKINGS.get(day, {}):
            return {"ok": False, "reason": "slot already taken"}
        BOOKINGS.setdefault(day, {})[time] = caller
        return {"ok": True, "day": day, "time": time, "name": caller}
    return {"error": "unknown tool"}


# Per-session conversation memory: {session_id: [messages]}
SESSIONS = {}


def get_reply(user_text: str, session_id: str = "default") -> str:
    messages = SESSIONS.setdefault(session_id, [])
    messages.append({"role": "user", "content": [{"text": user_text}]})

    while True:
        resp = brt.converse(
            modelId=MODEL_ID,
            system=[{"text": SYSTEM_PROMPT}],
            messages=messages,
            toolConfig={"tools": TOOLS},
        )
        out = resp["output"]["message"]
        messages.append(out)

        if resp.get("stopReason") == "tool_use":
            tool_results = []
            for block in out["content"]:
                if "toolUse" in block:
                    tu = block["toolUse"]
                    result = _run_tool(tu["name"], tu["input"])
                    tool_results.append({"toolResult": {
                        "toolUseId": tu["toolUseId"],
                        "content": [{"json": result}],
                    }})
            messages.append({"role": "user", "content": tool_results})
            continue

        return "".join(b.get("text", "") for b in out["content"])


if __name__ == "__main__":
    sid = "test"
    for turn in [
        "Hi, I'd like to book an appointment",
        "Tuesday please",
        "1 PM works, my name is Omar",
    ]:
        print("USER:", turn)
        print("AGENT:", get_reply(turn, sid), "\n")
