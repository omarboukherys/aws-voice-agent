"""The agent brain: text in -> text reply out, via Claude on Bedrock."""
import json
import boto3

brt = boto3.client("bedrock-runtime", region_name="us-east-1")
MODEL_ID = "us.anthropic.claude-haiku-4-5-20251001-v1:0"

SYSTEM_PROMPT = (
    "You are a friendly voice assistant answering phone-style calls. "
    "Keep replies short and natural, as if speaking out loud (1-3 sentences). "
    "Avoid lists, markdown, or long explanations. Be warm and concise."
)

def get_reply(user_text: str) -> str:
    resp = brt.converse(
        modelId=MODEL_ID,
        system=[{"text": SYSTEM_PROMPT}],
        messages=[{"role": "user", "content": [{"text": user_text}]}],
    )
    return resp["output"]["message"]["content"][0]["text"]

if __name__ == "__main__":
    print(get_reply("Hi, what can you help me with?"))
