# Technical Note — Snapdeal AI Virtual KAM

**Aarav** is a browser-based, voice-first AI Virtual Key Account Manager prototype designed around the supplied Snapdeal seller scenario. A seller can speak naturally, explain a business concern, and receive evidence-based recommendations through a two-way voice conversation.

## Model and voice workflow

The application uses the Gemini Live API through the `google-genai` Python SDK. The browser captures microphone audio and streams it to a FastAPI backend over WebSocket. Gemini Live processes the conversation and returns generated audio. Audio is streamed back to the browser for playback, while input/output transcriptions populate the conversation transcript. The system prompt instructs Aarav to understand English, Hindi and Hinglish but respond only in English.

## Business tools and reasoning

The backend exposes read-only tools for seller metrics, out-of-stock products and cancellation breakdowns. Aarav uses these tools to investigate the sample seller data: sales decline from ₹2,00,000 to ₹1,35,000, orders decline from 400 to 270, cancellation rate rises from 8% to 14%, average selling price remains ₹500, and out-of-stock products rise from 5 to 18.

The application distinguishes observed metrics from assumptions. SKU-level lost-order figures and cancellation reason percentages are illustrative mock data, not verified Snapdeal transaction records. Stock-outs are treated as a plausible contributor to the decline, not proven to be the sole cause.

## Human-approved actions

Restock selection is scope-aware: an explicit request for all unavailable products includes all 18 sample SKUs, while top-five and selected-SKU requests remain supported. The backend validates every selected SKU against the stock lookup.\n\nThe prototype supports three approval-based workflows: preparing a restock task, preparing a WhatsApp summary, and recording a follow-up request. Aarav first prepares an exact preview. The backend executes the corresponding mock handler only after the seller approves it on the dashboard. Declined actions are not executed. These are demo actions; no live Snapdeal inventory, WhatsApp, calendar or calling integration is connected.

## Follow-up intelligence

Approved follow-ups are stored in a local SQLite database with their due date, purpose and baseline metrics. A background monitor marks records due. For presentation purposes, **Test Follow-up Now** generates a clearly labelled simulated recovery report so the workflow can be demonstrated without waiting several days. Actual performance analysis would require fresh seller metrics from a real or separately refreshed data source.

## Technology

Python, FastAPI, WebSockets, Gemini Live API, `google-genai`, browser Web Audio APIs, HTML/CSS/JavaScript and SQLite.

**Scope:** This is a runnable prototype using mock seller data, built to demonstrate voice interaction, business reasoning, tool use, human approval and a dynamic dashboard. It is not a production Snapdeal integration.
