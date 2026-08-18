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


SYSTEM_PROMPT = (
    "You are a friendly voice receptionist for a clinic. You do two things: "
    "(1) book appointments (collect day, time, and the caller's name, using your booking tools), and "
    "(2) answer general questions about the business using the answer_faq tool "
    "(hours, location, services, payment, parking). "
    "Speak naturally and briefly (1-2 sentences), never use lists or markdown. "
    "If a slot is taken, offer alternatives. Always confirm a booking clearly."
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
    {
        "toolSpec": {
            "name": "answer_faq",
            "description": "Answer general questions about the business (hours, location, services, payment, parking).",
            "inputSchema": {"json": {
                "type": "object",
                "properties": {"question": {"type": "string", "description": "the caller's question"}},
                "required": ["question"],
            }},
        }
    },
]


_ddb = boto3.resource("dynamodb", region_name="us-east-1")
_table = _ddb.Table("voice-agent-bookings")


def _booked_times(day):
    resp = _table.query(
        KeyConditionExpression=boto3.dynamodb.conditions.Key("day").eq(day)
    )
    return {item["time"] for item in resp.get("Items", [])}

KNOWLEDGE_BASE = {
    "hours": "We are open Monday to Friday, 9 AM to 6 PM. We are closed on weekends.",
    "location": "We are located at 12 Rue Mohammed V, downtown. Parking is available nearby.",
    "services": "We offer consultations, follow-up visits, and specialist appointments.",
    "payment": "We accept cash, credit cards, and most insurance plans.",
    "parking": "Yes, free parking is available in front of the building.",
    "contact": "You can reach us by phone during business hours, or book directly here.",
}

def _run_tool(name, tool_input):
    day = tool_input.get("day", "").lower()
    if name == "check_availability":
        taken = _booked_times(day)
        free = [t for t in AVAILABILITY.get(day, []) if t not in taken]
        return {"day": day, "available": free} if free else {"day": day, "available": [], "note": "no slots"}
    if name == "book_appointment":
        time, caller = tool_input["time"], tool_input["name"]
        if time in _booked_times(day):
            return {"ok": False, "reason": "slot already taken"}
        _table.put_item(Item={"day": day, "time": time, "name": caller})
        return {"ok": True, "day": day, "time": time, "name": caller}
    if name == "answer_faq":
        q = tool_input.get("question", "").lower()
        for key, answer in KNOWLEDGE_BASE.items():
            if key in q:
                return {"answer": answer}
        # fallback: return the whole KB so the LLM can pick the best match
        return {"knowledge_base": KNOWLEDGE_BASE}
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
        "What are your opening hours?",
        "Do you have parking?",
        "I'd like to book an appointment on Friday at 10 AM, my name is Sara",
    ]:
        print("USER:", turn)
        print("AGENT:", get_reply(turn, sid), "\n")
