# app.py — PostHere: Groq + Supabase saving version (English)

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
# Credentials
# ───────────────────────────────────────────────
TWILIO_SID    = os.environ.get("TWILIO_ACCOUNT_SID")
TWILIO_TOKEN  = os.environ.get("TWILIO_AUTH_TOKEN")
TWILIO_NUMBER = os.environ.get("TWILIO_WHATSAPP_NUMBER", "whatsapp:+14155238886")
GROQ_KEY      = os.environ.get("GROQ_API_KEY")
DB_URL        = os.environ.get("DATABASE_URL")

twilio_client = Client(TWILIO_SID, TWILIO_TOKEN) if TWILIO_SID and TWILIO_TOKEN else None
groq_client   = Groq(api_key=GROQ_KEY) if GROQ_KEY else None

# Short-term memory: phone → list of messages
conversation_history = {}

# ───────────────────────────────────────────────
# System prompt – instructs Groq to output JSON when report is complete
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
6. When you believe you have enough information for a complete report (item type, description, location, at least one unique detail), output a JSON block at the END of your reply in this exact format:

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
   """
