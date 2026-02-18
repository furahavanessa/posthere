import os
import re
import json
from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse
from groq import Groq
from services import handle_report_and_match, check_db_for_matches
from database import get_session, save_session

app = Flask(__name__)
groq_client = Groq(api_key=os.environ.get("GROQ_API_KEY"))

SYSTEM_PROMPT = """
You are 'PostHere Goma'. Collect: 1. Item name 2. Quartier 3. Description 4. Secret detail.
If FOUND, ask for the 'drop_off_point' (Police station).
Never apologize or say you are an AI. Never lie about matches.
Output JSON only when complete:
{"type":"lost/found", "item":"...", "location":"...", "description":"...", "drop_off_point":"...", "unique_detail_1":"..."}
"""

@app.route("/", methods=['GET'])
def home():
    return "PostHere Goma is Live", 200

@app.route("/whatsapp", methods=['POST'])
def whatsapp():
    phone = request.values.get('From', '')
    message = request.values.get('Body', '').strip()
    msg_low = message.lower()

    # --- 1. BYPASS AI FOR TRUTH CHECK ---
    # If user asks "Did you find it?", we skip the AI and check the DB directly
    status_keywords = ["find", "found", "lost", "check", "news", "recherche", "match"]
    if any(k in msg_low for k in status_keywords) and len(msg_low.split()) < 6:
        result_text = check_db_for_matches(phone)
        resp = MessagingResponse()
        resp.message(result_text)
        return str(resp)

    # --- 2. AI DATA COLLECTION ---
    history = get_session(phone) or [{"role": "system", "content": SYSTEM_PROMPT}]
    history.append({"role": "user", "content": message})

    try:
        chat = groq_client.chat.completions.create(
            messages=history,
            model="llama-3.3-70b-versatile",
            temperature=0.2
        )
        ai_msg = chat.choices[0].message.content
    except Exception as e:
        print(f"Groq Error: {e}")
        ai_msg = "Sorry, I'm having trouble thinking. Try again in a moment."

    # --- 3. JSON & MATCHING ---
    json_match = re.search(r'\{.*\}', ai_msg, re.DOTALL)
    if json_match:
        try:
            data = json.loads(json_match.group())
            # Save report and notify others
            rep_id, matches = handle_report_and_match(data, phone)
            ai_msg = re.sub(r'\{.*\}', '', ai_msg).strip()
            
            if matches:
                ai_msg += "\n\n🚨 *MATCH FOUND!* We found a report matching yours in our database."
            else:
                ai_msg += "\n\n✅ Report filed. We will text you the moment a match appears."
        except:
            pass

    history.append({"role": "assistant", "content": ai_msg})
    save_session(phone, history[-10:])

    # --- 4. SECURE RETURN TO TWILIO ---
    resp = MessagingResponse()
    resp.message(ai_msg)
    return str(resp)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)