"""FastAPI voice agent server: receives mic audio, returns spoken reply."""
import asyncio
import base64
import boto3
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from amazon_transcribe.client import TranscribeStreamingClient
from amazon_transcribe.handlers import TranscriptResultStreamHandler
from amazon_transcribe.model import TranscriptEvent
from brain import get_reply

app = FastAPI()
polly = boto3.client("polly", region_name="us-east-1")
CHUNK = 1024 * 8


class Handler(TranscriptResultStreamHandler):
    def __init__(self, stream):
        super().__init__(stream)
        self.transcript = ""

    async def handle_transcript_event(self, event: TranscriptEvent):
        for result in event.transcript.results:
            if not result.is_partial:
                for alt in result.alternatives:
                    self.transcript = alt.transcript


async def transcribe_pcm(pcm: bytes) -> str:
    client = TranscribeStreamingClient(region="us-east-1")
    stream = await client.start_stream_transcription(
        language_code="en-US", media_sample_rate_hz=16000, media_encoding="pcm",
        vocabulary_name=None, show_speaker_label=False,
        enable_partial_results_stabilization=True, partial_results_stability="high",
    )

    async def send():
        for i in range(0, len(pcm), CHUNK):
            await stream.input_stream.send_audio_event(audio_chunk=pcm[i:i + CHUNK])
            await asyncio.sleep(0.01)
        await stream.input_stream.end_stream()

    handler = Handler(stream.output_stream)
    await asyncio.gather(send(), handler.handle_events())
    return handler.transcript


@app.get("/", response_class=HTMLResponse)
async def index():
    with open("static/index.html", encoding="utf-8") as f:
        return f.read()


@app.post("/talk")
async def talk(request: Request):
    session_id = request.headers.get("X-Session-Id", "anonymous")
    pcm = await request.body()
    user_text = await transcribe_pcm(pcm)
    if not user_text:
        return JSONResponse({"user": "", "reply": "Sorry, I didn't catch that.", "audio": ""})
    reply = get_reply(user_text, session_id=session_id)
    audio = polly.synthesize_speech(Text=reply, OutputFormat="mp3", VoiceId="Joanna")
    audio_b64 = base64.b64encode(audio["AudioStream"].read()).decode()
    return JSONResponse({"user": user_text, "reply": reply, "audio": audio_b64})
