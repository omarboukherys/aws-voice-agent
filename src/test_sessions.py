"""Verify two sessions keep separate memory."""
from brain import get_reply

# Alice books Monday
print("A1:", get_reply("I want an appointment Monday", "alice"))
# Bob books Friday
print("B1:", get_reply("I want an appointment Friday", "bob"))
# Alice continues - agent must still be on MONDAY, not Friday
print("A2:", get_reply("what times did you say?", "alice"))
# Bob continues - must be on FRIDAY
print("B2:", get_reply("what times did you say?", "bob"))
