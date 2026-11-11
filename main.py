
import asyncio
import json
import logging
import os
import uuid

from datetime import datetime, timedelta, timezone
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.websockets import WebSocketState

from google import genai
from google.genai import types

from prompt import SYSTEM_PROMPT
from tools import KamSession
import followups as followup_store


# ============================================================
# 1. CONFIGURATION
# ============================================================

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"

load_dotenv(BASE_DIR / ".env")

API_KEY = os.getenv("GEMINI_API_KEY")
MODEL = os.getenv("GEMINI_MODEL", "gemini-3.8-live")

# India Standard Time (UTC+05:30).
IST = timezone(timedelta(hours=5, minutes=30), name="IST")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s"
)

logger = logging.getLogger("snapdeal-kam")

app = FastAPI(
    title="Snapdeal Virtual KAM",
    description="AI-powered seller relationship management assistant",
    version="1.3.0"
)


# ============================================================
# 2. GEMINI CLIENT
# ============================================================

client = None

if API_KEY:
    client = genai.Client(
        api_key=API_KEY,
        http_options=types.HttpOptions(api_version="v1beta")
    )
else:
    logger.warning("GEMINI_API_KEY is missing.")


# ============================================================
# 3. TOOL DECLARATIONS
# ============================================================

TOOL_DECLARATIONS = [

    {
        "name": "get_seller_metrics",
        "description": (
            "Retrieve previous and current month seller metrics, "
            "including sales, orders, cancellation rate, average "
            "selling price and percentage changes."
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
            "Retrieve out-of-stock products, their SKU codes, product "
            "names, days out of stock, lost orders and estimated lost "
            "revenue. By default return ALL unavailable products. Use "
            "top_n only when the seller explicitly asks for a limited "
            "number such as the top five."
        ),
        "behavior": "BLOCKING",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "top_n": {
                    "type": "INTEGER",
                    "description": "Optional number of products. Omit this to retrieve all unavailable products."
                }
            }
        }
    },

    {
        "name": "get_cancellation_breakdown",
        "description": (
            "Retrieve cancellation rates and cancellation reasons."
        ),
        "behavior": "BLOCKING",
        "parameters": {
            "type": "OBJECT",
            "properties": {}
        }
    },

    {
        "name": "request_action_approval",
        "description": (
            "Prepare a business action for seller review. This tool "
            "does not execute anything. The backend displays an exact "
            "preview and waits for the seller to click Approve or "
            "Decline. Use only after explaining the proposed action "
            "and obtaining the seller's agreement to prepare it."
        ),
        "behavior": "BLOCKING",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {
                    "type": "STRING",
                    "enum": [
                        "create_restock_task",
                        "send_whatsapp_summary",
                        "schedule_followup_call"
                    ],
                    "description": "The action to prepare."
                },
                "skus": {
                    "type": "ARRAY",
                    "items": {"type": "STRING"},
                    "description": (
                        "SKU codes only when the seller explicitly requests "
                        "specific products. Do not use a five-SKU list to "
                        "represent a request for all unavailable products."
                    )
                },
                "scope": {
                    "type": "STRING",
                    "enum": ["all", "top_five", "selected"],
                    "description": (
                        "For restock: use all when the seller asks for all "
                        "unavailable products; top_five only when explicitly "
                        "requested; selected when specific SKUs are requested."
                    )
                },
                "priority": {
                    "type": "STRING",
                    "enum": ["low", "medium", "high"],
                    "description": "Restock task priority."
                },
                "message": {
                    "type": "STRING",
                    "description": (
                        "The complete WhatsApp summary to show for review."
                    )
                },
                "days_from_now": {
                    "type": "INTEGER",
                    "description": "Days until the proposed follow-up."
                },
                "purpose": {
                    "type": "STRING",
                    "description": "Purpose of the follow-up."
                }
            },
            "required": ["action"]
        }
    },

    {
        "name": "end_call",
        "description": (
            "End the current conversation when the seller clearly "
            "asks to end, disconnect, terminate, hang up or stop the "
            "call. Recognise equivalent clear Hindi and Hinglish "
            "requests. Do not use for ambiguous statements such as "
            "'Is that it?' or 'Anything else?'"
        ),
        "behavior": "BLOCKING",
        "parameters": {
            "type": "OBJECT",
            "properties": {}
        }
    }

]


ALLOWED_READ_TOOLS = {
    "get_seller_metrics",
    "get_out_of_stock_products",
    "get_cancellation_breakdown"
}

ALLOWED_ACTIONS = {
    "create_restock_task",
    "send_whatsapp_summary",
    "schedule_followup_call"
}


# ============================================================
# 4. AGENT INSTRUCTIONS
# ============================================================

AGENT_INSTRUCTIONS = """

LANGUAGE POLICY — HIGHEST PRIORITY

- Understand English, Hindi and Hinglish.
- Understand Hindi words spoken in English script.
- Always respond in English ONLY.
- Never speak Hindi, Hinglish or Telugu.
- Do not change response language based on seller input.
- Ask for clarification in English when input is unclear.

VOICE STYLE

- Warm, professional and conversational.
- Short, natural spoken responses.
- Ask one question at a time.
- Do not repeat greetings or answered questions.
- Allow the seller to interrupt.

SELLER CONTEXT

Seller: Rajesh
Store: Rajesh Traders
Category: Fashion & Accessories

Previous month:
- Sales: Rs. 2,00,000
- Orders: 400
- Cancellation rate: 8%
- Average selling price: Rs. 500
- Out of stock: 5 products

Current month:
- Sales: Rs. 1,35,000
- Orders: 270
- Cancellation rate: 14%
- Average selling price: Rs. 500
- Out of stock: 18 products

Sales and orders declined by 32.5%.

These observations do not prove the cause of the decline.

BUSINESS INVESTIGATION

- Retrieve seller metrics before discussing performance.
- Investigate stock availability when relevant.
- Investigate cancellation reasons when relevant.
- Never invent metrics or SKU information.
- Clearly distinguish facts, estimates and hypotheses.
- The cancellation reason breakdown is sample data based
  on assumptions, not verified transaction-level data.

RESTOCK ACTION

- Use actual SKU codes from the stock investigation.
- If the seller asks for ALL unavailable products or gives a count
  matching the total, set scope="all". The backend selects every
  verified unavailable SKU; never silently reduce the request to five.
- If the seller explicitly asks for the top five, set scope="top_five".
- If the seller names specific products, set scope="selected" and pass
  only those verified SKU codes.
- Do not invent SKUs or product names.
- The preview will contain product names, SKU codes,
  days out of stock and estimated lost orders where available.
- Explain that lost orders and revenue are estimates.

WHATSAPP SUMMARY ACTION

- Prepare a personalised message using the seller's findings.
- Include performance changes, key observations and
  practical recommendations.
- The exact message will appear in the approval preview.
- The demo records a mock action only.
- No real WhatsApp message is sent.

FOLLOW-UP ACTION

- Use the requested number of days.
- The backend calculates the exact proposed date in IST.
- No follow-up time is implied unless explicitly supplied.
- The demo records a mock action only.
- No real calendar appointment or phone call is booked.

APPROVAL POLICY

1. Explain the proposed action before preparing it.
2. Ask whether the seller wants the action prepared.
3. When they agree, call request_action_approval.
4. This creates a pending preview; it does not execute anything.
5. Tell the seller to review the preview on the dashboard.
6. The backend executes only after the seller clicks Approve.
7. A decline must never execute the action.
8. Never announce completion before the backend confirms it.
9. After execution, explicitly describe the operation as a mock action.
10. Never say a WhatsApp message was actually sent.
11. Never say a real follow-up call was booked.

CALL TERMINATION

When the seller clearly asks to end the call:
- Call end_call.
- Give a short farewell in English.
- Do not start another topic.
- Do not ask another question.
- The application closes the session after farewell playback.

Recognise clear requests such as:
- End the call.
- Let's end this call.
- Hang up.
- Terminate the call.
- Disconnect the call.
- Call band karo.
- Call khatam karo.

Do not terminate for ambiguous statements such as:
- Is that it?
- Anything else?
- Okay.
- Thank you.

CONVERSATION FLOW

1. Greet the seller once.
2. Explain the performance observation.
3. Understand seller concerns.
4. Investigate using business tools.
5. Explain findings and uncertainty.
6. Give exactly three practical recommendations.
7. Offer relevant mock actions with approval.
8. Summarise findings and next steps.

Always respond in English.

"""


# ============================================================
# 5. GEMINI LIVE CONFIGURATION
# ============================================================

GEMINI_CONFIG = types.LiveConnectConfig(
    response_modalities=[types.Modality.AUDIO],

    system_instruction=types.Content(
        parts=[
            types.Part(
                text=SYSTEM_PROMPT + "\n\n" + AGENT_INSTRUCTIONS
            )
        ]
    ),

    input_audio_transcription=types.AudioTranscriptionConfig(),
    output_audio_transcription=types.AudioTranscriptionConfig(),

    tools=[
        {
            "function_declarations": TOOL_DECLARATIONS
        }
    ]
)


# ============================================================
# 6. STOCK PRODUCT EXTRACTION
# ============================================================

def _normalise_key(key):
    return str(key).strip().lower().replace("-", "_").replace(" ", "_")


def _first_value(record, aliases):
    normalised = {
        _normalise_key(key): value
        for key, value in record.items()
    }

    for alias in aliases:
        value = normalised.get(alias)

        if value is not None and value != "":
            return value

    return None


def _number_or_none(value):
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def extract_stock_products(result):
    """
    Find SKU records in the existing get_out_of_stock_products result.
    Supports common field aliases and nested response structures.
    """

    products = []
    seen_skus = set()

    sku_aliases = (
        "sku",
        "sku_code",
        "sku_id",
        "product_sku",
        "product_code",
        "seller_sku",
        "listing_sku"
    )

    name_aliases = (
        "product_name",
        "name",
        "title",
        "product_title"
    )

    days_aliases = (
        "days_out_of_stock",
        "days_out",
        "days_out_of_stock_count",
        "out_of_stock_days"
    )

    orders_aliases = (
        "lost_orders",
        "estimated_lost_orders",
        "orders_lost",
        "lost_order_estimate"
    )

    revenue_aliases = (
        "estimated_lost_revenue",
        "lost_revenue",
        "revenue_lost",
        "estimated_revenue_lost"
    )

    last_month_aliases = (
        "last_month_orders",
        "previous_month_orders",
        "monthly_orders"
    )

    def walk(node):

        if isinstance(node, list):

            for item in node:
                walk(item)

            return

        if not isinstance(node, dict):
            return

        sku = _first_value(node, sku_aliases)

        if sku is not None:

            sku = str(sku).strip()

            if sku and sku not in seen_skus:

                seen_skus.add(sku)

                name = _first_value(node, name_aliases)

                product = {
                    "sku": sku,
                    "product_name": (
                        str(name).strip()
                        if name is not None
                        else "Product name unavailable"
                    ),
                    "days_out_of_stock": _number_or_none(
                        _first_value(node, days_aliases)
                    ),
                    "last_month_orders": _number_or_none(
                        _first_value(node, last_month_aliases)
                    ),
                    "estimated_lost_orders": _number_or_none(
                        _first_value(node, orders_aliases)
                    ),
                    "estimated_lost_revenue": _number_or_none(
                        _first_value(node, revenue_aliases)
                    )
                }

                products.append(product)

        for value in node.values():

            if isinstance(value, (dict, list)):
                walk(value)

    walk(result)

    return products


# ============================================================
# 7. DASHBOARD EVENT MAPPING
# ============================================================

def build_dashboard_event(tool_name, result):

    if tool_name == "get_seller_metrics":

        previous = result.get("last_month", {})
        current = result.get("this_month", {})

        return {
            "type": "dashboard_update",
            "section": "metrics",
            "data": {
                "seller": result.get("seller", {}),

                "sales": {
                    "current": current.get("sales"),
                    "previous": previous.get("sales"),
                    "change_pct": result.get("sales_change_pct")
                },

                "orders": {
                    "current": current.get("orders"),
                    "previous": previous.get("orders"),
                    "change_pct": result.get("orders_change_pct")
                },

                "stock": {
                    "current": current.get("out_of_stock"),
                    "previous": previous.get("out_of_stock")
                },

                "cancellations": {
                    "current_rate": current.get("cancellation_rate"),
                    "previous_rate": previous.get("cancellation_rate")
                }
            }
        }

    if tool_name == "get_out_of_stock_products":

        return {
            "type": "dashboard_update",
            "section": "stock_details",
            "data": {
                "products": extract_stock_products(result),
                "raw_result": result
            }
        }

    if tool_name == "get_cancellation_breakdown":

        return {
            "type": "dashboard_update",
            "section": "cancellation_details",
            "data": result
        }

    return None


# ============================================================
# 8. ACTION PREPARATION AND PREVIEW
# ============================================================

def prepare_action(action, arguments, stock_products):
    """
    Validate action inputs and build a complete human-reviewable
    preview. This function does not execute any action.
    """

    if action == "create_restock_task":

        requested_skus = arguments.get("skus") or []
        if not isinstance(requested_skus, list):
            raise ValueError("SKU list must be an array.")

        requested_skus = list(dict.fromkeys(
            str(sku).strip() for sku in requested_skus if str(sku).strip()
        ))

        available_by_sku = {
            product["sku"]: product for product in stock_products
        }
        scope = str(arguments.get("scope", "")).lower().strip()

        if scope == "all":
            selected = list(stock_products)
        elif scope == "top_five":
            selected = list(stock_products[:5])
        elif scope == "selected" or requested_skus:
            if not requested_skus:
                raise ValueError(
                    "Specific-product restock requires at least one SKU."
                )
            unknown = [
                sku for sku in requested_skus
                if sku not in available_by_sku
            ]
            if unknown:
                raise ValueError(
                    "These SKUs were not found in the complete stock lookup: "
                    + ", ".join(unknown)
                )
            selected = [available_by_sku[sku] for sku in requested_skus]
            scope = "selected"
        elif scope == "":
            # Safe default: never silently narrow an unspecified restock
            # request. Top five must be explicitly requested by the seller.
            selected = list(stock_products)
            scope = "all"
        else:
            raise ValueError("Restock scope must be all, top_five or selected.")

        if not selected:
            raise ValueError(
                "No verified out-of-stock SKU records are available."
            )

        priority = str(arguments.get("priority", "high")).lower()
        if priority not in {"low", "medium", "high"}:
            raise ValueError("Priority must be low, medium or high.")

        clean_arguments = {
            "skus": [item["sku"] for item in selected],
            "priority": priority,
            "scope": scope,
        }

        preview = {
            "kind": "restock",
            "scope": scope,
            "priority": priority,
            "total_out_of_stock": len(stock_products),
            "selected_count": len(selected),
            "products": selected,
            "disclosure": (
                "Product and lost-order figures are sample data. "
                "This approval creates a local demo task only."
            )
        }

        scope_label = {
            "all": "all",
            "top_five": "top five",
            "selected": "selected",
        }[scope]
        title = "Restock task — product review"
        description = (
            f"Review {len(selected)} {scope_label} unavailable products "
            f"before approving a {priority.upper()} priority mock restock task."
        )
        return clean_arguments, title, description, preview

    if action == "send_whatsapp_summary":

        message = str(
            arguments.get("message", "")
        ).strip()

        if not message:
            raise ValueError(
                "A complete WhatsApp summary is required."
            )

        if len(message) > 3000:
            raise ValueError(
                "WhatsApp summary must be 3000 characters or fewer."
            )

        clean_arguments = {
            "message": message
        }

        preview = {
            "kind": "whatsapp",
            "message": message,
            "disclosure": (
                "This is a preview of a mock WhatsApp action. "
                "No WhatsApp message will actually be sent."
            )
        }

        return (
            clean_arguments,
            "WhatsApp summary — message review",
            "Review the exact message below. Approval records the mock action only.",
            preview
        )

    if action == "schedule_followup_call":

        days = arguments.get("days_from_now")

        if isinstance(days, bool) or not isinstance(days, int):
            raise ValueError(
                "Follow-up days must be a whole number."
            )

        if days < 1 or days > 30:
            raise ValueError(
                "Follow-up must be between 1 and 30 days from now."
            )

        purpose = str(
            arguments.get("purpose", "")
        ).strip()

        if not purpose:
            raise ValueError(
                "A follow-up purpose is required."
            )

        if len(purpose) > 500:
            raise ValueError("Follow-up purpose is too long.")

        proposed_datetime = (
            datetime.now(IST) + timedelta(days=days)
        )

        proposed_date = proposed_datetime.date()

        date_label = proposed_date.strftime("%A, %d %B %Y")

        clean_arguments = {
            "days_from_now": days,
            "purpose": purpose
        }

        preview = {
            "kind": "followup",
            "days_from_now": days,
            "date_iso": proposed_date.isoformat(),
            "date_label": date_label,
            "timezone": "IST (UTC+05:30)",
            "time_label": "Not specified",
            "purpose": purpose,
            "disclosure": (
                "This is a mock follow-up record. "
                "No real calendar appointment or phone call is booked."
            )
        }

        return (
            clean_arguments,
            "Follow-up — schedule review",
            f"Review the proposed follow-up date: {date_label}.",
            preview
        )

    raise ValueError("Unsupported business action.")


# ============================================================
# 9. COMPLETION MESSAGES
# ============================================================

def action_completion_message(action, arguments, preview):

    if action == "create_restock_task":

        return (
            "The mock restock task has been recorded successfully for "
            f"{len(arguments['skus'])} verified unavailable products. "
            "The exact SKU list is available in the dashboard. "
            "No actual Snapdeal inventory has been changed."
        )

    if action == "send_whatsapp_summary":

        return (
            "The mock WhatsApp summary action has been recorded "
            "successfully. The message was prepared and stored in "
            "this demo, but no actual WhatsApp message was sent."
        )

    if action == "schedule_followup_call":

        return (
            "The mock follow-up record has been created for "
            + preview["date_label"]
            + ". The time was not specified. No real phone call "
            "or calendar appointment has been booked."
        )

    return "The mock action was recorded."


# ============================================================
# 10. STATIC FRONTEND
# ============================================================

if STATIC_DIR.is_dir():

    app.mount(
        "/static",
        StaticFiles(directory=str(STATIC_DIR)),
        name="static"
    )


@app.get("/")
async def home():

    index_file = STATIC_DIR / "index.html"

    if not index_file.is_file():

        return JSONResponse(
            status_code=503,
            content={
                "status": "frontend_missing",
                "message": "Create static/index.html."
            }
        )

    return FileResponse(index_file)


@app.get("/health")
async def health():

    return {
        "status": "running",
        "model": MODEL,
        "api_key_configured": bool(API_KEY),
        "frontend_available": (
            STATIC_DIR / "index.html"
        ).is_file(),
        "approval_based_actions_enabled": True
    }


# ============================================================
# 10A. PERSISTENT FOLLOW-UP API
# ============================================================

@app.get("/api/followups")
async def api_list_followups():
    return {"followups": followup_store.list_followups()}


@app.post("/api/followups/{followup_id}/test-now")
async def api_test_followup_now(followup_id: str):
    """Run a clearly labelled simulated follow-up immediately."""
    try:
        record = followup_store.complete_with_simulated_report(followup_id)
        return {"status": "completed", "followup": record}
    except ValueError as error:
        return JSONResponse(status_code=404, content={"error": str(error)})


async def followup_scheduler_loop():
    while True:
        try:
            changed = followup_store.scheduler_tick()
            if changed:
                logger.info("Marked %s follow-up(s) as due", changed)
        except Exception:
            logger.exception("Follow-up scheduler tick failed")
        await asyncio.sleep(30)


# ============================================================
# 11. WEBSOCKET VOICE SESSION
# ============================================================

@app.websocket("/ws")
async def voice_session(websocket: WebSocket):

    await websocket.accept()

    if client is None:

        await websocket.send_json({
            "type": "error",
            "message": "GEMINI_API_KEY is missing from .env"
        })

        await websocket.close(code=1011)
        return

    kam = KamSession()

    pending_actions = {}

    stock_products_cache = []

    end_call_requested = False

    end_call_ack = asyncio.Event()
    session_finished = asyncio.Event()

    gemini_send_lock = asyncio.Lock()

    logger.info("Seller browser connected")

    try:

        async with client.aio.live.connect(
            model=MODEL,
            config=GEMINI_CONFIG
        ) as session:

            logger.info("Gemini Live connected: %s", MODEL)

            async def send_text_to_gemini(text):

                async with gemini_send_lock:
                    await session.send_realtime_input(text=text)

            async def send_audio_to_gemini(audio):

                async with gemini_send_lock:
                    await session.send_realtime_input(
                        audio=types.Blob(
                            data=audio,
                            mime_type="audio/pcm;rate=16000"
                        )
                    )

            async def send_tool_responses(responses):

                async with gemini_send_lock:
                    await session.send_tool_response(
                        function_responses=responses
                    )

            await websocket.send_json({
                "type": "status",
                "message": "Connected to Aarav"
            })

            await send_text_to_gemini(
                "Start a new conversation with Rajesh. "
                "First retrieve his seller metrics. Greet him "
                "naturally in English, explain the main observation "
                "briefly and ask one relevant question. Always "
                "respond in English."
            )

            # =================================================
            # BROWSER -> GEMINI / APPROVAL EXECUTION
            # =================================================

            async def browser_to_gemini():

                while True:

                    incoming = await websocket.receive()

                    if incoming["type"] == "websocket.disconnect":

                        logger.info("Browser disconnected")
                        return

                    text_data = incoming.get("text")

                    if text_data is not None:

                        try:
                            payload = json.loads(text_data)
                        except json.JSONDecodeError:
                            logger.warning("Invalid browser JSON")
                            continue

                        message_type = payload.get("type")

                        # -------------------------------------
                        # CALL END ACK
                        # -------------------------------------

                        if message_type == "call_ended_ack":

                            end_call_ack.set()
                            await session_finished.wait()
                            return

                        # -------------------------------------
                        # ACTION APPROVAL OR DECLINE
                        # -------------------------------------

                        if message_type in {
                            "approve_action",
                            "reject_action"
                        }:

                            request_id = str(
                                payload.get("request_id", "")
                            )

                            pending = pending_actions.pop(
                                request_id,
                                None
                            )

                            if pending is None:

                                await websocket.send_json({
                                    "type": "action_result",
                                    "request_id": request_id,
                                    "status": "expired",
                                    "message": (
                                        "This approval request is "
                                        "no longer available."
                                    )
                                })

                                continue

                            action = pending["action"]
                            arguments = pending["arguments"]
                            preview = pending["preview"]

                            if message_type == "approve_action":

                                logger.info(
                                    "Seller approved action: %s",
                                    action
                                )

                                try:

                                    # Execute only after seller approval.
                                    result = kam.call(action, arguments)

                                    followup_record = None
                                    if action == "schedule_followup_call":
                                        baseline = kam.call("get_seller_metrics")
                                        followup_record = followup_store.create_followup(
                                            days_from_now=arguments["days_from_now"],
                                            purpose=arguments["purpose"],
                                            baseline=baseline
                                        )
                                        result["followup_record"] = followup_record
                                        logger.info(
                                            "Persistent follow-up saved: %s",
                                            followup_record["id"]
                                        )

                                    completion = action_completion_message(
                                        action,
                                        arguments,
                                        preview
                                    )

                                    await websocket.send_json({
                                        "type": "action_result",
                                        "request_id": request_id,
                                        "action": action,
                                        "status": "completed",
                                        "result": result,
                                        "followup": followup_record,
                                        "message": completion
                                    })

                                    logger.info(
                                        "Mock action completed: %s",
                                        action
                                    )

                                    await send_text_to_gemini(
                                        "The seller explicitly approved "
                                        f"{action}. The backend confirms "
                                        "the mock handler executed. Tell "
                                        "the seller this result accurately: "
                                        + completion
                                        + " Respond briefly in English. "
                                        "Do not imply any production "
                                        "Snapdeal integration."
                                    )

                                except Exception as action_error:

                                    logger.exception(
                                        "Mock action execution failed"
                                    )

                                    await websocket.send_json({
                                        "type": "action_result",
                                        "request_id": request_id,
                                        "action": action,
                                        "status": "failed",
                                        "message": str(action_error)
                                    })

                                    await send_text_to_gemini(
                                        "The seller approved the action, "
                                        "but the backend reported this "
                                        "error: "
                                        + str(action_error)
                                        + ". Explain that it failed. "
                                        "Do not claim it succeeded."
                                    )

                            else:

                                logger.info(
                                    "Seller declined action: %s",
                                    action
                                )

                                await websocket.send_json({
                                    "type": "action_result",
                                    "request_id": request_id,
                                    "action": action,
                                    "status": "declined",
                                    "message": (
                                        "The seller declined. "
                                        "No action was executed."
                                    )
                                })

                                await send_text_to_gemini(
                                    "The seller declined the proposed "
                                    f"{action}. No action was executed. "
                                    "Acknowledge politely in English "
                                    "without pressuring the seller."
                                )

                            continue

                        # -------------------------------------
                        # OPTIONAL TEXT INPUT
                        # -------------------------------------

                        if message_type == "text":

                            user_text = str(
                                payload.get("text", "")
                            ).strip()

                            if user_text and not end_call_requested:

                                await send_text_to_gemini(user_text)

                    # -----------------------------------------
                    # MICROPHONE AUDIO
                    # -----------------------------------------

                    audio_data = incoming.get("bytes")

                    if audio_data and not end_call_requested:

                        await send_audio_to_gemini(audio_data)

            # =================================================
            # GEMINI -> BROWSER / TOOL EXECUTION
            # =================================================

            async def gemini_to_browser():

                nonlocal end_call_requested
                nonlocal stock_products_cache

                while True:

                    async for message in session.receive():

                        # -------------------------------------
                        # TOOL CALLS
                        # -------------------------------------

                        if message.tool_call:

                            function_responses = []

                            for function_call in (
                                message.tool_call.function_calls
                            ):

                                tool_name = function_call.name

                                arguments = dict(
                                    function_call.args or {}
                                )

                                logger.info(
                                    "Function requested: %s",
                                    tool_name
                                )

                                # =================================
                                # END CALL
                                # =================================

                                if tool_name == "end_call":

                                    end_call_requested = True

                                    await websocket.send_json({
                                        "type": "call_ending",
                                        "message": "Aarav is ending the call."
                                    })

                                    function_responses.append(
                                        types.FunctionResponse(
                                            id=function_call.id,
                                            name=tool_name,
                                            response={
                                                "status": "success",
                                                "message": (
                                                    "Seller requested "
                                                    "termination. Give a "
                                                    "brief farewell in English."
                                                )
                                            }
                                        )
                                    )

                                    continue

                                # =================================
                                # ACTION APPROVAL PREVIEW
                                # =================================

                                if tool_name == "request_action_approval":

                                    try:

                                        action = arguments.get("action")

                                        if action not in ALLOWED_ACTIONS:
                                            raise ValueError(
                                                "Unsupported business action."
                                            )

                                        # Always refresh the complete stock list
                                        # before preparing a restock action. A
                                        # previous top-N investigation may have
                                        # cached only a partial list.
                                        if action == "create_restock_task":

                                            await websocket.send_json({
                                                "type": "tool_activity",
                                                "name": "get_out_of_stock_products",
                                                "status": "running"
                                            })

                                            stock_result = kam.call(
                                                "get_out_of_stock_products",
                                                {}
                                            )

                                            stock_products_cache = (
                                                extract_stock_products(
                                                    stock_result
                                                )
                                            )

                                            stock_event = build_dashboard_event(
                                                "get_out_of_stock_products",
                                                stock_result
                                            )

                                            if stock_event:
                                                await websocket.send_json(
                                                    stock_event
                                                )

                                            await websocket.send_json({
                                                "type": "tool_activity",
                                                "name": "get_out_of_stock_products",
                                                "status": "completed"
                                            })

                                        (
                                            clean_arguments,
                                            title,
                                            description,
                                            preview
                                        ) = prepare_action(
                                            action,
                                            arguments,
                                            stock_products_cache
                                        )

                                        request_id = uuid.uuid4().hex[:12]

                                        pending_actions[request_id] = {
                                            "action": action,
                                            "arguments": clean_arguments,
                                            "preview": preview
                                        }

                                        await websocket.send_json({
                                            "type": "pending_action",
                                            "request_id": request_id,
                                            "action": action,
                                            "title": title,
                                            "description": description,
                                            "preview": preview,
                                            "status": "pending"
                                        })

                                        tool_result = {
                                            "status": "approval_required",
                                            "request_id": request_id,
                                            "message": (
                                                "The complete action preview "
                                                "has been displayed. Nothing "
                                                "has been executed. The seller "
                                                "must review and approve it."
                                            )
                                        }

                                        logger.info(
                                            "Action staged for approval: %s",
                                            action
                                        )

                                    except Exception as validation_error:

                                        logger.exception(
                                            "Action preparation failed"
                                        )

                                        tool_result = {
                                            "status": "error",
                                            "message": str(validation_error)
                                        }

                                    function_responses.append(
                                        types.FunctionResponse(
                                            id=function_call.id,
                                            name=tool_name,
                                            response=tool_result
                                        )
                                    )

                                    continue

                                # =================================
                                # READ-ONLY BUSINESS TOOLS
                                # =================================

                                if tool_name not in ALLOWED_READ_TOOLS:

                                    tool_result = {
                                        "status": "error",
                                        "message": "Tool is not permitted."
                                    }

                                    await websocket.send_json({
                                        "type": "tool_activity",
                                        "name": tool_name,
                                        "status": "failed"
                                    })

                                else:

                                    await websocket.send_json({
                                        "type": "tool_activity",
                                        "name": tool_name,
                                        "status": "running"
                                    })

                                    try:

                                        result = kam.call(
                                            tool_name,
                                            arguments
                                        )

                                        tool_result = {
                                            "status": "ok",
                                            "result": result
                                        }

                                        if (
                                            tool_name ==
                                            "get_out_of_stock_products"
                                        ):

                                            stock_products_cache = (
                                                extract_stock_products(result)
                                            )

                                        dashboard_event = (
                                            build_dashboard_event(
                                                tool_name,
                                                result
                                            )
                                        )

                                        if dashboard_event:

                                            await websocket.send_json(
                                                dashboard_event
                                            )

                                        await websocket.send_json({
                                            "type": "tool_activity",
                                            "name": tool_name,
                                            "status": "completed"
                                        })

                                        logger.info(
                                            "Read-only tool completed: %s",
                                            tool_name
                                        )

                                    except Exception as tool_error:

                                        logger.exception(
                                            "Business tool failed: %s",
                                            tool_name
                                        )

                                        tool_result = {
                                            "status": "error",
                                            "message": str(tool_error)
                                        }

                                        await websocket.send_json({
                                            "type": "tool_activity",
                                            "name": tool_name,
                                            "status": "failed"
                                        })

                                function_responses.append(
                                    types.FunctionResponse(
                                        id=function_call.id,
                                        name=tool_name,
                                        response=tool_result
                                    )
                                )

                            if function_responses:

                                await send_tool_responses(
                                    function_responses
                                )

                        # -------------------------------------
                        # MODEL RESPONSE
                        # -------------------------------------

                        content = message.server_content

                        if content is None:
                            continue

                        input_transcription = getattr(
                            content,
                            "input_transcription",
                            None
                        )

                        if (
                            input_transcription
                            and input_transcription.text
                        ):

                            await websocket.send_json({
                                "type": "user_transcript",
                                "text": input_transcription.text
                            })

                        output_transcription = getattr(
                            content,
                            "output_transcription",
                            None
                        )

                        if (
                            output_transcription
                            and output_transcription.text
                        ):

                            await websocket.send_json({
                                "type": "assistant_transcript",
                                "text": output_transcription.text
                            })

                        if content.model_turn:

                            for part in content.model_turn.parts:

                                if (
                                    part.inline_data
                                    and part.inline_data.data is not None
                                ):

                                    audio_data = part.inline_data.data

                                    if isinstance(audio_data, bytes):

                                        await websocket.send_bytes(
                                            audio_data
                                        )

                        if content.turn_complete:

                            await websocket.send_json({
                                "type": "turn_complete"
                            })

                            if end_call_requested:

                                await websocket.send_json({
                                    "type": "call_ended",
                                    "message": "Call ended successfully."
                                })

                                try:

                                    await asyncio.wait_for(
                                        end_call_ack.wait(),
                                        timeout=12
                                    )

                                except asyncio.TimeoutError:

                                    logger.warning(
                                        "Call-end acknowledgement timed out"
                                    )

                                session_finished.set()

                                logger.info(
                                    "Seller voice session terminated"
                                )

                                return

                    logger.info(
                        "Gemini response turn completed. "
                        "Listening for next turn."
                    )

            # =================================================
            # RUN BOTH STREAMS
            # =================================================

            browser_task = asyncio.create_task(
                browser_to_gemini()
            )

            gemini_task = asyncio.create_task(
                gemini_to_browser()
            )

            tasks = [
                browser_task,
                gemini_task
            ]

            done, pending = await asyncio.wait(
                tasks,
                return_when=asyncio.FIRST_COMPLETED
            )

            for task in pending:
                task.cancel()

            await asyncio.gather(
                *pending,
                return_exceptions=True
            )

            for task in done:

                try:
                    task.result()

                except WebSocketDisconnect:
                    logger.info("WebSocket disconnected normally")

                except asyncio.CancelledError:
                    pass

    except WebSocketDisconnect:

        logger.info("Seller browser disconnected")

    except Exception as error:

        logger.exception("Voice session error")

        try:

            await websocket.send_json({
                "type": "error",
                "message": str(error)
            })

        except Exception:
            pass

    finally:

        pending_actions.clear()

        if websocket.client_state == WebSocketState.CONNECTED:

            try:

                await websocket.close(
                    code=1000,
                    reason="Voice session finished"
                )

            except Exception:
                pass

        logger.info("Virtual KAM session closed")


# ============================================================
# 12. STARTUP AND SHUTDOWN
# ============================================================

@app.on_event("startup")
async def startup_event():

    followup_store.init_db()
    app.state.followup_scheduler_task = asyncio.create_task(
        followup_scheduler_loop()
    )

    logger.info("---------------------------------------")
    logger.info("Snapdeal Virtual KAM starting")
    logger.info("Model: %s", MODEL)
    logger.info("API key configured: %s", bool(API_KEY))
    logger.info("Frontend: %s", STATIC_DIR)
    logger.info("Dynamic dashboard: enabled")
    logger.info("Detailed action previews: enabled")
    logger.info("Approval-based mock actions: enabled")
    logger.info("Voice termination: enabled")
    logger.info("---------------------------------------")


@app.on_event("shutdown")
async def shutdown_event():

    logger.info("Snapdeal Virtual KAM shutting down")
