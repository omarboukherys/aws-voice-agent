"""Full voice pipeline: audio file -> STT -> brain -> TTS -> reply audio."""
import asyncio
import boto3
from amazon_transcribe.client import TranscribeStreamingClient
from amazon_transcribe.handlers import TranscriptResultStreamHandler
from amazon_transcribe.model import TranscriptEvent
from brain import get_reply

CHUNK = 1024 * 8
polly = boto3.client("polly", region_name="us-east-1")


class Handler(TranscriptResultStreamHandler):
    def __init__(self, stream):
        super().__init__(stream)
        self.transcript = ""

    async def handle_transcript_event(self, event: TranscriptEvent):
        for result in event.transcript.results:
            if not result.is_partial:
                for alt in result.alternatives:
                    self.transcript = alt.transcript


async def transcribe(path: str) -> str:
    client = TranscribeStreamingClient(region="us-east-1")
    stream = await client.start_stream_transcription(
        language_code="en-US", media_sample_rate_hz=16000, media_encoding="pcm",
    )

    async def send():
        with open(path, "rb") as f:
            while chunk := f.read(CHUNK):
                await stream.input_stream.send_audio_event(audio_chunk=chunk)
                await asyncio.sleep(0.1)
        await stream.input_stream.end_stream()

    handler = Handler(stream.output_stream)
    await asyncio.gather(send(), handler.handle_events())
    return handler.transcript


def speak(text: str, out_path: str):
    resp = polly.synthesize_speech(Text=text, OutputFormat="mp3", VoiceId="Joanna")
    with open(out_path, "wb") as f:
        f.write(resp["AudioStream"].read())


async def main():
    user_text = await transcribe("test_input.pcm")
    print("USER (heard):", user_text)

    reply = get_reply(user_text)
    print("AGENT (says):", reply)

    speak(reply, "reply.mp3")
    print("-> saved reply.mp3")


if __name__ == "__main__":
    asyncio.run(main())
