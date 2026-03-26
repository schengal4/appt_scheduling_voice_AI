import json
import logging
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import JSONResponse
from availability import check_availability, book_appointment
import os

logger = logging.getLogger("vapi.webhook")
router = APIRouter()

VAPI_SECRET = os.environ["VAPI_WEBHOOK_SECRET"]   # set this in your .env


def handle_check_availability(args: dict) -> dict:
    provider    = args.get("provider")
    preference  = args.get("preference")   # optional — "tuesday", "morning", etc.

    if not provider:
        return {"error": "provider is required"}

    return check_availability(provider, preference)


def handle_book_appointment(args: dict) -> dict:
    provider     = args.get("provider")
    datetime_str = args.get("datetime")
    patient_name = args.get("patient_name")

    missing = [f for f, v in [("provider", provider), ("datetime", datetime_str), ("patient_name", patient_name)] if not v]
    if missing:
        return {"error": f"Missing required fields: {', '.join(missing)}"}

    return book_appointment(provider, datetime_str, patient_name)


TOOL_HANDLERS = {
    "check_availability": handle_check_availability,
    "book_appointment":   handle_book_appointment,
}


@router.post("/vapi/webhook")
async def vapi_webhook(request: Request):
    payload = await request.json()
    message = payload.get("message", {})
    event   = message.get("type")
    call_id = message.get("call", {}).get("id", "unknown")

    logger.info(f"[{call_id}] event={event}")

    # ── Tool calls — must return results ──────────────────────────────────────
    if event == "tool-calls":
        results = []
        for tc in message.get("toolCallList", []):
            name = tc.get("name") or tc.get("function", {}).get("name")
            args = tc.get("arguments") or tc.get("function", {}).get("arguments", {})
            if isinstance(args, str):
                args = json.loads(args)

            tool_id = tc.get("id")

            logger.info(f"[{call_id}] tool={name} args={args}")

            handler = TOOL_HANDLERS.get(name)
            if handler:
                result = handler(args)
            else:
                result = {"error": f"Unknown tool: {name}"}

            logger.info(f"[{call_id}] tool={name} result={result}")

            results.append({
                "toolCallId": tool_id,
                "result":     json.dumps(result),   # Vapi requires a string
            })

        return JSONResponse({"results": results})

    # ── Inbound call — assign assistant dynamically ───────────────────────────
    elif event == "assistant-request":
        # For now return the default assistant
        # Later: look up caller's prior transcript and inject context
        return JSONResponse({"assistantId": os.environ["VAPI_ASSISTANT_ID"]})

    # ── End of call — save transcript for callback memory ────────────────────
    elif event == "end-of-call-report":
        artifact = message.get("artifact", {})
        messages = artifact.get("messagesOpenAIFormatted", [])
        summary  = message.get("analysis", {}).get("summary", "")
        caller   = message.get("call", {}).get("customer", {}).get("number", "")

        # TODO: persist to DB — for now just log
        logger.info(f"[{call_id}] call ended. caller={caller} turns={len(messages)} summary={summary[:80]}")

        return JSONResponse({})

    # ── All other informational events — just ack ─────────────────────────────
    else:
        return JSONResponse({})