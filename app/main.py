import os
import logging
from pathlib import Path
from fastapi import FastAPI, Request, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from openai import AsyncOpenAI
from app.knowledge_base import SYSTEM_PROMPT
from app.manychat import send_message

BASE_DIR = Path(__file__).resolve().parent.parent
STATIC_DIR = BASE_DIR / "static"

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Otterly Spotless Chatbot")

# Fallback client using env var — used by /webhook (ManyChat)
default_openai_client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))

conversation_history: dict[str, list[dict]] = {}

app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/")
async def root():
    return FileResponse(str(STATIC_DIR / "index.html"))


def get_history(subscriber_id: str) -> list[dict]:
    if subscriber_id not in conversation_history:
        conversation_history[subscriber_id] = []
    return conversation_history[subscriber_id]


async def get_ai_reply(
    subscriber_id: str,
    user_message: str,
    system_prompt: str,
    client: AsyncOpenAI,
) -> str:
    history = get_history(subscriber_id)
    history.append({"role": "user", "content": user_message})

    trimmed = history[-10:]

    response = await client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "system", "content": system_prompt}] + trimmed,
        max_tokens=300,
        temperature=0.7,
    )

    reply = response.choices[0].message.content.strip()
    history.append({"role": "assistant", "content": reply})
    return reply


def build_response(reply: str) -> dict:
    return {
        "version": "v2",
        "content": {
            "messages": [{"type": "text", "text": reply}]
        }
    }


def build_system_prompt(business_info: str) -> str:
    if business_info.strip():
        return SYSTEM_PROMPT + f"\n\n## EXTRA BUSINESS DETAILS (from settings)\n{business_info}"
    return SYSTEM_PROMPT


@app.post("/chat")
async def chat(request: Request):
    """Web frontend endpoint — accepts optional api_key and business_info from UI."""
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON")

    subscriber_id  = body.get("subscriber_id", "web_user")
    user_message   = body.get("last_message") or body.get("message", "")
    api_key        = body.get("api_key", "").strip()
    business_info  = body.get("business_info", "").strip()

    if not user_message:
        raise HTTPException(status_code=400, detail="Missing message")

    # Use key from UI if provided, otherwise fall back to env var
    client = AsyncOpenAI(api_key=api_key) if api_key else default_openai_client
    system_prompt = build_system_prompt(business_info)

    try:
        reply = await get_ai_reply(subscriber_id, user_message, system_prompt, client)
    except Exception as e:
        logger.error(f"OpenAI error: {e}")
        if "api_key" in str(e).lower() or "authentication" in str(e).lower():
            reply = "Invalid API key. Please check the key in Settings above."
        else:
            reply = "Sorry, I'm having trouble right now. Please call us at (470) 298-8884!"

    return build_response(reply)


@app.post("/webhook")
async def webhook(request: Request):
    """ManyChat External Request block — uses env var API key and default knowledge base."""
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON")

    subscriber_id = body.get("subscriber_id")
    user_message  = body.get("last_message") or body.get("message", "")
    first_name    = body.get("first_name", "")

    if not subscriber_id or not user_message:
        raise HTTPException(status_code=400, detail="Missing subscriber_id or message")

    logger.info(f"ManyChat message from {first_name} ({subscriber_id}): {user_message}")

    try:
        reply = await get_ai_reply(
            subscriber_id, user_message, SYSTEM_PROMPT, default_openai_client
        )
    except Exception as e:
        logger.error(f"Error: {e}")
        reply = "Sorry, something went wrong! Please call us at (470) 298-8884."

    return build_response(reply)


@app.get("/health")
async def health():
    return {"status": "running", "service": "Otterly Spotless Chatbot"}
