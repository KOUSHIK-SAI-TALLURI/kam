
import asyncio
import os

from dotenv import load_dotenv
from google import genai
from google.genai import types


# Load environment variables from .env
load_dotenv()

API_KEY = os.getenv("GEMINI_API_KEY")
MODEL = os.getenv("GEMINI_MODEL", "gemini-3.8-live")


# Validate API key
if not API_KEY:
    raise ValueError(
        "GEMINI_API_KEY is missing. Check your .env file."
    )


# Initialize Gemini client using the Live API version
client = genai.Client(
    api_key=API_KEY,
    http_options=types.HttpOptions(
        api_version="v1beta"
    )
)


async def main():

    print(f"Connecting to {MODEL}...")

    # Configure Gemini Live
    config = types.LiveConnectConfig(
        response_modalities=[types.Modality.AUDIO],

        system_instruction=types.Content(
            parts=[
                types.Part(
                    text=(
                        "You are a friendly and professional "
                        "AI business assistant. "
                        "Keep your spoken responses concise."
                    )
                )
            ]
        ),

        # Receive a text transcript of Gemini's spoken response
        output_audio_transcription=types.AudioTranscriptionConfig(),
    )

    try:
        async with client.aio.live.connect(
            model=MODEL,
            config=config
        ) as session:

            print("Connected to Gemini Live!")
            print("Sending test message...")

            # Send real-time text input
            await session.send_realtime_input(
                text=(
                    "Say hello and introduce yourself "
                    "as a virtual business assistant."
                )
            )

            print("\nGemini response:")

            audio_bytes_received = 0

            # Receive Gemini's response
            async for message in session.receive():

                server_content = message.server_content

                if server_content is None:
                    continue

                # Print text transcription of spoken response
                if server_content.output_transcription:
                    transcript = (
                        server_content.output_transcription.text
                    )

                    if transcript:
                        print(transcript, end="", flush=True)

                # Count received audio data
                if server_content.model_turn:

                    for part in server_content.model_turn.parts:

                        if (
                            part.inline_data
                            and part.inline_data.data is not None
                        ):

                            audio_data = part.inline_data.data

                            if isinstance(audio_data, bytes):
                                audio_bytes_received += len(audio_data)

                # Stop when Gemini finishes its response
                if server_content.turn_complete:
                    break

            print("\n")

            print("Audio bytes received:", audio_bytes_received)

            if audio_bytes_received > 0:
                print("SUCCESS: Gemini Live API is working!")
            else:
                print(
                    "WARNING: No audio received. "
                    "Check the response and configuration."
                )

    except Exception as error:

        print("\nGemini Live connection or response failed:")
        print(type(error).__name__, error)


if __name__ == "__main__":
    asyncio.run(main())
