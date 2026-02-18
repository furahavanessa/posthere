import os
import json
import re
from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse
from twilio.rest import Client
from dotenv import load_dotenv
from groq import Groq
import psycopg2
from psycopg2.extras import RealDictCursor

load_dotenv()

app = Flask(__name__)

# ───────────────────────────────────────────────
# Load credentials
# ───────────────────────────────────────────────
TWILIO_SID    = os.environ.get("TWILIO_ACCOUNT_SID")
TWILIO_TOKEN  = os.environ.get("TWILIO_AUTH_TOKEN")
TWILIO_NUMBER = os.environ.get("TWILIO_WHATSAPP_NUMBER", "whatsapp:+14155238886")

GROQ_KEY      = os.environ.get("GROQ_API_KEY")
DB_URL        = os.environ.get("DATABASE_URL")

twilio_client = Client(TWILIO_SID, TWILIO_TOKEN) if TWILIO_SID and TWILIO_TOKEN else None
groq_client   = Groq(api_key=GROQ_KEY) if GROQ_KEY else None

# Per-user short-term memory: phone → list of messages
conversation_history = {}

# ───────────────────────────────────────────────
# System prompt — controls when JSON is produced
# ───────────────────────────────────────────────
SYSTEM_PROMPT = """
You are PostHere — the official, trustworthy Lost & Found assistant for Goma (DRC).

Your goals in EVERY reply:
1. Always be very reassuring: "We are taking your case very seriously and actively working on it."
2. When someone says they found something:
   - Thank them sincerely for their honesty.
   - Strongly encourage them to bring the item to the nearest police station as soon as possible.
   - Give a concrete example address:
     → Main Police Station (Commissariat Central): Inside Goma City Hall (Mairie de Goma), central area, near Avenue du 30 Juin and the central market.
     → If they mention a neighborhood (Les Volcans, Karisimbi, Mugunga, etc.), suggest the closest police post.
3. When someone says they lost something:
   - Carefully collect details (item, description, location, brand, color, unique features).
   - Reassure them strongly that you are checking existing reports and will notify them of matches.
   - Still advise them to file an official report at the police station.
4. Be helpful, calm, professional and warm. Use natural English.
5. Never give out phone numbers directly — all handovers go through the police.
6. When you believe you have enough information for a complete report (item type, description, location, at least one unique detail), output a JSON block **at the END** of your reply in this exact format:

   ```json
   {
     "type": "lost" or "found",
     "item": "short item name",
     "description": "full description",
     "location": "where it was lost/found",
     "unique_detail_1": "first secret/detail",
     "unique_detail_2": "second secret/detail (optional)",
     "phone": "user's phone number if known"
   }
Do NOT output JSON unless the report is complete enough to save.
Keep normal conversation replies outside the JSON block.
"""
def get_db_connection():
return psycopg2.connect(
DB_URL,
cursor_factory=RealDictCursor,
sslmode='require'
)
def save_report_to_db(report: dict, phone: str):
"""Save structured report to Supabase"""
conn = get_db_connection()
cur = conn.cursor()
try:
cur.execute("""
INSERT INTO items
(status, item_name, description, location, secret1, secret2, phone_number, created_at, match_status)
VALUES (%s, %s, %s, %s, %s, %s, %s, NOW(), 'open')
RETURNING id
""", (
report.get("type", "unknown"),
report.get("item", "").lower().strip(),
report.get("description", ""),
report.get("location", ""),
report.get("unique_detail_1", "").strip().lower(),
report.get("unique_detail_2", "").strip().lower(),
phone
))
new_id = cur.fetchone()["id"]
conn.commit()
print(f"[DB] Saved report ID {new_id} for {phone}")
return new_id
except Exception as e:
print("[DB ERROR]", str(e))
conn.rollback()
return None
finally:
cur.close()
conn.close()
def get_groq_reply(phone: str, user_text: str) -> str:
if phone not in conversation_history:
conversation_history[phone] = [{"role": "system", "content": SYSTEM_PROMPT}]
conversation_history[phone].append({"role": "user", "content": user_text})
try:
completion = groq_client.chat.completions.create(
model="llama-3.1-70b-versatile",
messages=conversation_history[phone],
temperature=0.65,
max_tokens=600
)
raw_reply = completion.choices[0].message.content.strip()
except Exception as e:
print("Groq error:", str(e))
raw_reply = "Sorry, I'm having a technical issue right now. Please try again in a minute."
conversation_history[phone].append({"role": "assistant", "content": raw_reply})
Limit memory
if len(conversation_history[phone]) > 15:
conversation_history[phone] = [conversation_history[phone][0]] + conversation_history[phone][-14:]
Try to extract JSON block
json_match = re.search(r'json\s*(.*?)\s*', raw_reply, re.DOTALL | re.IGNORECASE)
if json_match:
try:
json_str = json_match.group(1).strip()
report_data = json.loads(json_str)
saved_id = save_report_to_db(report_data, phone)
if saved_id:
raw_reply = raw_reply.replace(json_match.group(0), "").strip()
raw_reply += "\n\nYour report has been successfully registered and saved securely. Thank you for helping keep Goma safer!"
else:
raw_reply += "\n\n(We had trouble saving the report — please try again later.)"
except Exception as e:
print("[JSON/save error]", str(e))
raw_reply += "\n\n(We had trouble processing the report — please try again.)"
return raw_reply
───────────────────────────────────────────────
WhatsApp webhook endpoint
───────────────────────────────────────────────
@app.route("/whatsapp", methods=["POST"])
@app.route("/whatsapp/", methods=["POST"])
def whatsapp_webhook():
msg_body = (request.values.get("Body") or "").strip()
sender = request.values.get("From")
print(f"[{sender}] Received: {msg_body!r}")
resp = MessagingResponse()
reply = resp.message()
ai_response = get_groq_reply(sender, msg_body)
reply.body(ai_response)
return str(resp)
if name == "main":
port = int(os.environ.get("PORT", 5000))
app.run(host="0.0.0.0", port=port, debug=True)
