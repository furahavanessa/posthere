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

# Strict Prompt to prevent the AI from making up stories
SYSTEM_PROMPT = """
You are 'PostHere Goma'. You ONLY record lost/found items.
DO NOT tell stories. DO NOT say an owner was found unless the system tells you so.
If the user asks 'Did someone lose/find this?', tell them: 'Let me check the official records...'
When a report is done, output ONLY this JSON:
{"type":"lost/found", "item":"...", "location":"...", "description":"...", "drop_off_point":"...", "unique_detail_1":"..."}
"""

@app.route("/whatsapp", methods=['POST'])
def whatsapp():
    phone = request.values.get('From', '')
    message = request.values.get('Body', '').strip()
    msg_low = message.lower()

    # --- 1. THE TRUTH FILTER (Bypass AI for database queries) ---
    # If the user asks "Did someone lose/find...", we go straight to the DB.
    search_keywords = ["did someone", "found?", "lost?", "match", "anyone report", "est-ce que"]
    if any(k in msg_low for k in search_keywords):
        # This function in services.py looks at the REAL database
        result_text = check_db_for_matches(phone)
        resp = MessagingResponse()
        resp.message(result_text)
        return str(resp)

    # --- 2. AI DATA ENTRY FLOW ---
    history = get_session(phone) or [{"role": "system", "content": SYSTEM_PROMPT}]
    history.append({"role": "user", "content": message})

    try:
        chat = groq_client.chat.completions.create(
            messages=history,
            model="llama-3.3-70b-versatile",
            temperature=0.1 # Very low to prevent storytelling
        )
        ai_msg = chat.choices[0].message.content
    except:
        ai_msg = "Service temporarily busy. Try again."

    # --- 3. JSON EXTRACTION ---
    json_match = re.search(r'\{.*\}', ai_msg, re.DOTALL)
    if json_match:
        try:
            data = json.loads(json_match.group())
            # Save and trigger proactive notification
            rep_id, matches = handle_report_and_match(data, phone)
            ai_msg = re.sub(r'\{.*\}', '', ai_msg).strip()
            
            if matches:
                ai_msg += "\n\n🚨 *SYSTEM MATCH:* We found a match! Check with the Mairie de Goma."
            else:
                ai_msg += "\n\n✅ Registered. We will text you the moment a match is found."
        except:
            pass

    history.append({"role": "assistant", "content": ai_msg})
    save_session(phone, history[-10:])

    resp = MessagingResponse()
    resp.message(ai_msg)
    return str(resp)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)