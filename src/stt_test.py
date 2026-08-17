"""Test Amazon Transcribe streaming on a PCM file."""
import asyncio
from amazon_transcribe.client import TranscribeStreamingClient
from amazon_transcribe.handlers import TranscriptResultStreamHandler
from amazon_transcribe.model import TranscriptEvent

CHUNK = 1024 * 8

class Handler(TranscriptResultStreamHandler):
    async def handle_transcript_event(self, event: TranscriptEvent):
        for result in event.transcript.results:
            if not result.is_partial:
                for alt in result.alternatives:
                    print("FINAL:", alt.transcript)

async def run():
    client = TranscribeStreamingClient(region="us-east-1")
    stream = await client.start_stream_transcription(
        language_code="en-US",
        media_sample_rate_hz=16000,
        media_encoding="pcm",
    )

    async def send_audio():
        with open("test_input.pcm", "rb") as f:
            while chunk := f.read(CHUNK):
                await stream.input_stream.send_audio_event(audio_chunk=chunk)
                await asyncio.sleep(0.1)
        await stream.input_stream.end_stream()

    handler = Handler(stream.output_stream)
    await asyncio.gather(send_audio(), handler.handle_events())

asyncio.run(run())
