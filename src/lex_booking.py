"""Lex V2 fulfillment for AppointmentBot: books into DynamoDB."""
import boto3

ddb = boto3.resource("dynamodb", region_name="us-east-1")
table = ddb.Table("voice-agent-bookings")

AVAILABILITY = {
    "monday": ["9:00 AM", "11:00 AM", "2:00 PM"],
    "tuesday": ["10:00 AM", "1:00 PM", "4:00 PM"],
    "wednesday": ["9:00 AM", "3:00 PM"],
    "thursday": ["11:00 AM", "2:00 PM", "4:00 PM"],
    "friday": ["10:00 AM", "1:00 PM"],
}


def _slot(slots, name):
    s = slots.get(name)
    return s["value"]["interpretedValue"] if s and s.get("value") else None


def _norm(s):
    return s.lower().replace(" ", "").replace(":00", "").replace(".", "")


def _close(intent_name, message, state="Fulfilled"):
    return {
        "sessionState": {
            "dialogAction": {"type": "Close"},
            "intent": {"name": intent_name, "state": state},
        },
        "messages": [{"contentType": "PlainText", "content": message}],
    }


def lambda_handler(event, context):
    intent = event["sessionState"]["intent"]
    slots = intent.get("slots", {})

    day = (_slot(slots, "Day") or "").strip().lower()
    time = (_slot(slots, "Time") or "").strip()
    name = (_slot(slots, "Name") or "").strip()
    print(f"SLOTS day={day!r} time={time!r} name={name!r}")

    day = next((d for d in AVAILABILITY if d in day), day)

    if day not in AVAILABILITY:
        return _close(intent["name"], "Sorry, we only book Monday to Friday. Which weekday would you like?")

    taken = {i["time"] for i in table.query(
        KeyConditionExpression=boto3.dynamodb.conditions.Key("day").eq(day)
    ).get("Items", [])}
    free = [t for t in AVAILABILITY[day] if t not in taken]

    match = next((t for t in free if time and _norm(time) in _norm(t)), None)

    if not match:
        opts = ", ".join(free) if free else "no slots left"
        return _close(intent["name"], f"On {day}, available times are {opts}. Which one would you like?")

    table.put_item(Item={"day": day, "time": match, "name": name or "Guest"})
    return _close(intent["name"], f"All set{', ' + name if name else ''}! Your appointment is booked for {day} at {match}.")
