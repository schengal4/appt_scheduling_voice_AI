import os
from dotenv import load_dotenv
load_dotenv(".env_file")  # loads .env file

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from vapi import AsyncVapi
import logging

# ── Config ─────────────────────────────────────────────────────────────────────
PHONE_NUMBER_ID = "10eb3b86-9cf4-44e2-b606-1e7c8605f928"
ASSISTANT_ID    = "c7c9d185-4155-4293-84fe-d99cad75a02f"

app    = FastAPI(title="Wellness Partners — Riley")
client = AsyncVapi(token=os.environ["VAPI_API_KEY"])
logging.basicConfig(filename="log.txt", level=logging.DEBUG)

# ── Phone utilities ─────────────────────────────────────────────────────────────
def normalize_phone(number: str) -> str:
    # Works for US numbers. Edge case: doesn't work for UK without +44.
    digits = ''.join(filter(str.isdigit, number))
    if len(digits) == 10:
        return f"+1{digits}"
    elif len(digits) == 11 and digits.startswith("1"):
        return f"+{digits}"
    return f"+{digits}"

def validate_phone(number: str) -> str:
    normalized = normalize_phone(number)
    digits = ''.join(filter(str.isdigit, normalized))
    if len(digits) < 10 or len(digits) > 15:
        raise HTTPException(status_code=400, detail=f"Invalid phone number: {number}")
    return normalized

# ── Vapi call endpoints ─────────────────────────────────────────────────────────
@app.post("/start_call")
async def start_call(phone_number: str):
    call = await client.calls.create(
        customer={"number": validate_phone(phone_number)},
        phone_number_id=PHONE_NUMBER_ID,
        assistant_id=ASSISTANT_ID,
    )
    return {"id": call.id, "status": call.status}

@app.get("/get_call_status")
async def get_call_status(call_id: str):
    call = await client.calls.get(call_id)
    return {"status": call.status}

@app.get("/get_call_messages")
async def get_call_messages(call_id: str):
    call = await client.calls.get(call_id)
    return extract_messages(call.messages)

def extract_messages(vapi_messages):
    result = {"system": None, "conversation": []}
    for msg in vapi_messages:
        if msg.role == "system":
            result["system"] = msg.message
        elif msg.role == "bot":
            result["conversation"].append({"role": "assistant", "content": msg.message})
        elif msg.role == "user":
            result["conversation"].append({"role": "user", "content": msg.message})
    return result["conversation"]

# ── Chat + webhook routers ──────────────────────────────────────────────────────
from chat    import router as chat_router
from webhook import router as webhook_router
app.include_router(chat_router)
app.include_router(webhook_router)

# ── Frontend ────────────────────────────────────────────────────────────────────
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/")
async def index():
    return FileResponse("static/index.html")

@app.get("/health")
async def health():
    return {"status": "ok"}