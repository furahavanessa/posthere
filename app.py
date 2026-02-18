import os
import re
import json
from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse
from groq import Groq
from services import handle_report_and_match, check_db_for_matches
from database import get_session, save_session, execute_query

app = Flask(__name__)
groq_client = Groq(api_key=os.environ.get("GROQ_API_KEY"))

SYSTEM_PROMPT = """
You are 'PostHere Goma'. Your ONLY job is to collect 4 things:
1. What was lost/found. 2. The Quartier. 3. Description. 4. A unique secret detail.
If FOUND, also ask for the 'drop_off_point' (police station).
Never say 'I am an AI'. Never hallucinate matches. 
When details are complete, output JSON:
{"type":"lost/found", "item":"...", "location":"...", "description":"...", "drop_off_point":"...", "unique_detail_1":"..."}
"""

@app.route("/whatsapp", methods=['POST'])
def whatsapp():
    phone = request.values.get('From', '')
    message = request.values.get('Body', '').strip()
    msg_low = message.lower()

    # --- 1. THE TRUTH ENGINE (Bypass AI for Status Checks) ---
    status_keywords = ["find", "trouvé", "check", "news", "anything", "recherche", "match"]
    if any(k in msg_low for k in status_keywords):
        response_text = check_db_for_matches(phone)
        resp = MessagingResponse()
        resp.message(response_text)
        return str(resp)

    # --- 2. AI CONVERSATION (Only for Data Entry) ---
    history = get_session(phone) or [{"role": "system", "content": SYSTEM_PROMPT}]
    history.append({"role": "user", "content": message})

    try:
        chat = groq_client.chat.completions.create(
            messages=history,
            model="llama-3.3-70b-versatile",
            temperature=0.2
        )
        ai_msg = chat.choices[0].message.content
    except:
        ai_msg = "System busy, please try again."

    # --- 3. JSON EXTRACTION ---
    json_match = re.search(r'\{.*\}', ai_msg, re.DOTALL)
    if json_match:
        try:
            data = json.loads(json_match.group())
            rep_id, matches = handle_report_and_match(data, phone)
            ai_msg = re.sub(r'\{.*\}', '', ai_msg).strip()
            if matches:
                ai_msg += "\n\n🚨 *MATCH DETECTED!* We found a report matching yours in our database."
            else:
                ai_msg += "\n\n✅ Report filed. I will text you the moment a match appears."
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