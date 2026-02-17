# app.py — PostHere: Groq-powered WhatsApp bot with database awareness
#          English version – reassures, pushes police handover for found items

import os
import random
from datetime import datetime
from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse
from twilio.rest import Client
from dotenv import load_dotenv
from groq import Groq

# ───────────────────────────────────────────────
#  Load credentials
# ───────────────────────────────────────────────

load_dotenv()

app = Flask(__name__)

TWILIO_SID    = os.environ.get("TWILIO_ACCOUNT_SID")
TWILIO_TOKEN  = os.environ.get("TWILIO_AUTH_TOKEN")
TWILIO_NUMBER = os.environ.get("TWILIO_WHATSAPP_NUMBER", "whatsapp:+14155238886")
GROQ_KEY      = os.environ.get("GROQ_API_KEY")

twilio_client = Client(TWILIO_SID, TWILIO_TOKEN) if TWILIO_SID and TWILIO_TOKEN else None
groq_client   = Groq(api_key=GROQ_KEY) if GROQ_KEY else None

# In-memory short-term memory per user (phone → list of messages)
conversation_history = {}

# ───────────────────────────────────────────────
#  System prompt – controls personality & rules
# ───────────────────────────────────────────────

SYSTEM_PROMPT = """You are PostHere — the official, trustworthy Lost & Found assistant for Goma (DRC).

Your goals in EVERY reply:
1. Always be very reassuring: "We are taking your case seriously and actively working on it."
2. When someone says they **found** something:
   - Thank them sincerely for their honesty.
   - Strongly encourage them to bring the item to the nearest police station as soon as possible.
   - Give a concrete example address:
     → Main Police Station (Commissariat Central): Inside Goma City Hall (Mairie de Goma), central area, near Avenue du 30 Juin and the central market.
     → If they mention a neighborhood (Les Volcans, Karisimbi, Mugunga, etc.), suggest the closest police post.
3. When someone says they **lost** something:
   - Collect clear details (what, description, color, brand, location, unique features).
   - Reassure them strongly that you are checking existing reports and will notify them of matches.
   - Still advise them to file an official report at the police station.
4. Be helpful, calm, professional and warm. Use natural English.
5. Never give out phone numbers directly — all real handovers go through the police.
6. If you think there is a possible match with existing reports, say so and ask for more confirmation details.

Keep answers short and focused — one clear step at a time.
"""

def get_groq_reply(phone: str, user_text: str) -> str:
    """Call Groq with conversation history + system prompt"""
    if phone not in conversation_history:
        conversation_history[phone] = [{"role": "system", "content": SYSTEM_PROMPT}]

    # Append user message
    conversation_history[phone].append({"role": "user", "content": user_text})

    try:
        completion = groq_client.chat.completions.create(
            model="llama-3.1-70b-versatile",
            messages=conversation_history[phone],
            temperature=0.65,
            max_tokens=450,
            top_p=0.92
        )
        reply_text = completion.choices[0].message.content.strip()
    except Exception as e:
        print("Groq call failed:", str(e))
        reply_text = (
            "Sorry, I'm having a technical issue right now. "
            "Please try again in a minute or contact support."
        )

    # Save assistant reply to history
    conversation_history[phone].append({"role": "assistant", "content": reply_text})

    # Limit memory (keep system + last 14 turns)
    if len(conversation_history[phone]) > 15:
        conversation_history[phone] = [conversation_history[phone][0]] + conversation_history[phone][-14:]

    return reply_text


def send_whatsapp(to_number: str, text: str) -> bool:
    """Send outbound WhatsApp message via Twilio"""
    if not twilio_client:
        print(f"[DRY RUN] → {to_number}: {text[:80]}...")
        return False
    try:
        msg = twilio_client.messages.create(
            from_=TWILIO_NUMBER,
            body=text,
            to=to_number
        )
        print(f"Sent to {to_number} – SID: {msg.sid}")
        return True
    except Exception as e:
        print(f"Twilio send failed: {e}")
        return False


@app.route("/whatsapp", methods=["POST"])
def whatsapp_webhook():
    msg_body = (request.values.get("Body") or "").strip()
    sender = request.values.get("From")

    print(f"[{sender}] Received: {msg_body!r}")

    resp = MessagingResponse()
    reply = resp.message()

    # Get intelligent reply from Groq
    ai_response = get_groq_reply(sender, msg_body)

    reply.body(ai_response)
    return str(resp)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
