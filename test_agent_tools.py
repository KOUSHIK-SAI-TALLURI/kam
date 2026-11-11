
import asyncio
import os

from dotenv import load_dotenv
from google import genai
from google.genai import types

from prompt import SYSTEM_PROMPT
from tools import KamSession


# Load environment variables
load_dotenv()

API_KEY = os.getenv("GEMINI_API_KEY")
MODEL = os.getenv("GEMINI_MODEL", "gemini-3.8-live")

if not API_KEY:
    raise ValueError("GEMINI_API_KEY is missing from .env")


# Initialize Gemini client
client = genai.Client(
    api_key=API_KEY,
    http_options=types.HttpOptions(api_version="v1beta")
)


# Read-only business tools available to Gemini
TOOL_DECLARATIONS = [
    {
        "name": "get_seller_metrics",
        "description": (
            "Retrieve the seller's current and previous month business "
            "metrics, including sales, orders, cancellations and "
            "percentage changes. Use this before discussing performance."
        ),
        "behavior": "BLOCKING",
        "parameters": {
            "type": "OBJECT",
            "properties": {}
        }
    },
    {
        "name": "get_out_of_stock_products",
        "description": (
            "Retrieve the seller's out-of-stock products, including "
            "SKU details and estimated lost orders or revenue. "
            "Use this when investigating stock availability."
        ),
        "behavior": "BLOCKING",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "top_n": {
                    "type": "INTEGER",
                    "description": (
                        "Number of top out-of-stock products to retrieve."
                    )
                }
            }
        }
    },
    {
        "name": "get_cancellation_breakdown",
        "description": (
            "Retrieve the seller's cancellation rates and the "
            "breakdown of cancellation reasons."
        ),
        "behavior": "BLOCKING",
        "parameters": {
            "type": "OBJECT",
            "properties": {}
        }
    }
]


# Gemini Live configuration
CONFIG = types.LiveConnectConfig(
    response_modalities=[types.Modality.AUDIO],

    system_instruction=types.Content(
        parts=[
            types.Part(
                text=(
                    SYSTEM_PROMPT
                    + "\n\n"
                    + "Tool usage rules:\n"
                    + "1. Use get_seller_metrics before discussing "
                    + "the seller's performance.\n"
                    + "2. Use out-of-stock and cancellation tools "
                    + "when relevant to the conversation.\n"
                    + "3. Never invent metrics or treat estimates "
                    + "as confirmed facts.\n"
                    + "4. These tools are read-only. Do not claim "
                    + "to have taken any business action.\n"
                    + "5. Do not make more than two consecutive "
                    + "tool calls without speaking to the seller."
                )
            )
        ]
    ),

    output_audio_transcription=types.AudioTranscriptionConfig(),

    tools=[
        {
            "function_declarations": TOOL_DECLARATIONS
        }
    ]
)


async def main():

    # Each test gets its own seller session
    kam = KamSession()

    # Separate counter for read-only tool calls
    tool_calls_made = 0

    # Track generated audio
    audio_bytes_received = 0

    print(f"Connecting to {MODEL}...")

    try:

        async with client.aio.live.connect(
            model=MODEL,
            config=CONFIG
        ) as session:

            print("Connected to Gemini Live!")
            print("Starting seller-agent test...\n")

            # Start the seller conversation
            await session.send_realtime_input(
                text=(
                    "Start the seller conversation with Rajesh. "
                    "First inspect his business metrics using your "
                    "available tool. Then explain the main observation "
                    "briefly and ask one relevant question."
                )
            )

            # Receive Gemini responses and tool requests
            async for message in session.receive():

                # Handle function calls from Gemini
                if message.tool_call:

                    function_responses = []

                    for function_call in message.tool_call.function_calls:

                        tool_calls_made += 1

                        name = function_call.name
                        args = dict(function_call.args or {})

                        print(f"\n[TOOL REQUEST] {name}")
                        print("[ARGUMENTS]", args)

                        try:

                            # Execute the Python business tool
                            result = kam.call(name, args)

                            response_data = {
                                "status": "ok",
                                "retryable": False,
                                "result": result
                            }

                            print("[TOOL RESULT]", result)

                        except Exception as error:

                            response_data = {
                                "status": "error",
                                "retryable": False,
                                "message": str(error)
                            }

                            print("[TOOL ERROR]", error)

                        # Prepare tool response for Gemini
                        function_responses.append(
                            types.FunctionResponse(
                                id=function_call.id,
                                name=name,
                                response=response_data
                            )
                        )

                    # Send results back to Gemini
                    await session.send_tool_response(
                        function_responses=function_responses
                    )

                    print("[TOOL RESPONSE SENT]\n")

                # Handle Gemini's response
                content = message.server_content

                if content is None:
                    continue

                # Print transcription of generated speech
                if content.output_transcription:

                    transcript = content.output_transcription.text

                    if transcript:
                        print(transcript, end="", flush=True)

                # Count generated audio
                if content.model_turn:

                    for part in content.model_turn.parts:

                        if (
                            part.inline_data
                            and part.inline_data.data is not None
                        ):

                            audio_data = part.inline_data.data

                            if isinstance(audio_data, bytes):
                                audio_bytes_received += len(audio_data)

                # Stop after Gemini completes its response
                if content.turn_complete:
                    break

            # Print test summary
            print("\n\n--- TEST SUMMARY ---")

            print("Read-only tool calls:", tool_calls_made)

            print("Mock business actions:", len(kam.actions))

            print("Audio bytes received:", audio_bytes_received)

            if audio_bytes_received > 0:
                print("SUCCESS: Gemini generated spoken audio!")
            else:
                print("WARNING: No audio received.")

            print("Recorded business actions:", kam.actions)

    except Exception as error:

        print("\nAgent test failed:")
        print(type(error).__name__, error)


if __name__ == "__main__":
    asyncio.run(main())
