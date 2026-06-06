import httpx
import os

MANYCHAT_API_URL = "https://api.manychat.com/fb/sending/sendContent"
MANYCHAT_API_KEY = os.getenv("MANYCHAT_API_KEY")


async def send_message(subscriber_id: str, text: str) -> bool:
    """Send a text message back to a ManyChat subscriber."""
    headers = {
        "Authorization": f"Bearer {MANYCHAT_API_KEY}",
        "Content-Type": "application/json",
    }

    payload = {
        "subscriber_id": subscriber_id,
        "data": {
            "version": "v2",
            "content": {
                "messages": [
                    {
                        "type": "text",
                        "text": text,
                    }
                ]
            },
        },
        "message_tag": "ACCOUNT_UPDATE",
    }

    async with httpx.AsyncClient() as client:
        response = await client.post(MANYCHAT_API_URL, json=payload, headers=headers)
        response.raise_for_status()
        return response.json().get("status") == "success"
