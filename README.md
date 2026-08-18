# AWS Voice Agent — Appointment Booking (two approaches)

A voice-driven appointment-booking assistant on AWS, built two ways:

1. **Custom voice pipeline** (web) — Amazon Transcribe (STT) -> Claude on Bedrock (reasoning + tools) -> Amazon Polly (TTS), served by FastAPI.
2. **Telephony voicebot** (phone) — Amazon Connect -> Amazon Lex -> Lambda -> DynamoDB, callable on a real phone number.

Both share the same booking logic and the same DynamoDB store.

## Why two approaches

The custom pipeline shows low-level control of the speech stack (streaming STT, LLM tool-calling, TTS). The Connect path shows the production-standard way to put a voicebot on a real phone line. Together they demonstrate both depth and the pragmatic AWS-native choice.

## Architecture

```
WEB (custom pipeline)
  Browser mic -> FastAPI -> Transcribe (STT) -> Claude/Bedrock (agent + tools) -> Polly (TTS) -> Browser

PHONE (Amazon Connect)
  Caller -> Connect flow -> Lex (AppointmentBot) -> Lambda -> DynamoDB -> spoken confirmation
```

Shared store: DynamoDB table `voice-agent-bookings` (day + time as keys, caller name as attribute).

## Intelligence & resilience

- **Tool-using agent** (web): Claude decides when to call `check_availability` and `book_appointment` rather than following a fixed script.
- **Per-session memory**: conversations are indexed by `session_id`, so concurrent callers never mix (verified with a two-session test).
- **Durable state**: bookings persist in DynamoDB; a taken slot is rejected on the next request.
- **Graceful handling**: unknown days, taken slots, and misheard input are answered with helpful re-prompts instead of failing.

## Stack

- **Speech**: Amazon Transcribe (streaming STT), Amazon Polly (TTS)
- **Reasoning**: Claude (Haiku) via Amazon Bedrock, tool-calling
- **Telephony**: Amazon Connect (claimed DID number, published contact flow) + Amazon Lex V2
- **Compute/State**: AWS Lambda (Python), Amazon DynamoDB
- **App**: FastAPI, Python

## Files

```
src/
  brain.py          Tool-using booking agent (Bedrock + tools + session memory)
  server.py         FastAPI: mic audio -> STT -> agent -> TTS
  pipeline.py       CLI end-to-end test of the voice loop
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

Amazon Connect instance + Lex bot `AppointmentBot` + Lambda `voice-lex-booking` wired to a published contact flow attached to a claimed number. Calling the number books by voice, end to end.

## Cost

Fully serverless / pay-per-use. Transcribe, Polly, Bedrock (Haiku), Lambda, DynamoDB and a Connect DID number cost cents for development and demos.

## Roadmap

- [ ] Continuous conversation (VAD) in the web client
- [ ] Cancel / reschedule intents
- [ ] Call recording + transcript storage for QA
- [ ] Multi-language (Polly + Lex locales)
