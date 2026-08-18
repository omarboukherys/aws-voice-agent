# AWS Voice Agent — Conversational Appointment & FAQ Assistant

An end-to-end conversational AI agent on AWS, built two ways: a custom voice pipeline and a real telephony voicebot. The agent books appointments, answers business questions from a knowledge base, and runs behind AI safeguards with performance monitoring.

## Two approaches

1. **Custom voice pipeline** (web) — Amazon Transcribe (STT) -> Claude on Bedrock (agent + tools) -> Amazon Polly (TTS), served by FastAPI.
2. **Telephony voicebot** (phone) — Amazon Connect -> Amazon Lex -> Lambda -> DynamoDB, callable on a real phone number.

Both share the same booking logic and DynamoDB store.

## What the agent does

- **Books appointments**: multi-turn dialogue collecting day, time, and name; checks live availability and persists to DynamoDB (taken slots rejected).
- **Answers questions (Knowledge Base)**: an `answer_faq` tool lets the agent respond to hours, location, services, payment, and parking questions, not just bookings.
- **Runs safely (AI governance)**: Amazon Bedrock Guardrails block PII (card numbers, passwords), prompt attacks, and toxic content on every turn.
- **Is observable**: each turn logs structured JSON metrics (latency, tool calls, token usage) for performance monitoring and optimization.

## Architecture

```
WEB (custom pipeline)
  Browser mic -> FastAPI -> Transcribe (STT) -> Claude/Bedrock (agent + tools + Guardrails) -> Polly (TTS)

PHONE (Amazon Connect)
  Caller -> Connect flow -> Lex (AppointmentBot) -> Lambda -> DynamoDB -> spoken confirmation
```

Agent tools: `check_availability`, `book_appointment`, `answer_faq`.
Shared store: DynamoDB `voice-agent-bookings`.
Safeguards: Bedrock Guardrail (PII block + content filters).

## Intelligence & resilience

- **Tool-using agent**: Claude decides when to book, check availability, or answer a FAQ.
- **Per-session memory**: conversations indexed by `session_id`; concurrent callers never mix (verified).
- **Durable state**: bookings persist in DynamoDB across restarts.
- **Guardrails**: sensitive input is blocked before it reaches the model (verified: a card number is rejected in ~800 ms, no tokens spent).
- **Monitoring**: per-turn latency / tool-calls / tokens emitted as JSON for CloudWatch.

## Stack

- **Speech**: Amazon Transcribe (streaming STT), Amazon Polly (TTS)
- **Reasoning**: Claude (Haiku) via Amazon Bedrock, tool-calling
- **Governance**: Amazon Bedrock Guardrails
- **Telephony**: Amazon Connect + Amazon Lex V2
- **Compute/State**: AWS Lambda (Python), Amazon DynamoDB
- **App**: FastAPI, Python

## Files

```
src/
  brain.py          Tool-using agent (booking + FAQ + Guardrails + metrics)
  server.py         FastAPI: mic audio -> STT -> agent -> TTS
  pipeline.py       CLI end-to-end voice-loop test
  lex_booking.py    Lambda: Lex V2 fulfillment -> DynamoDB
  stt_test.py       Transcribe streaming test
  test_sessions.py  Concurrency / isolation test
static/
  index.html        Push-to-talk web client
```

## Run (web pipeline)

```bash
pip install fastapi uvicorn boto3 amazon-transcribe
uvicorn server:app --app-dir src --port 8000
# open http://localhost:8000, hold the button and speak
```

## Run (telephony)

Amazon Connect instance + Lex bot `AppointmentBot` + Lambda `voice-lex-booking`, wired to a published contact flow on a claimed number. Calling the number books by voice, end to end.

## Cost

Fully serverless / pay-per-use: Transcribe, Polly, Bedrock (Haiku), Guardrails, Lambda, DynamoDB, and a Connect DID number cost cents for development and demos.

## Roadmap

- [ ] Continuous conversation (VAD) in the web client
- [ ] Cancel / reschedule intents
- [ ] Outbound webhook on booking (notify external systems)
- [ ] Multi-language (Polly + Lex locales)
