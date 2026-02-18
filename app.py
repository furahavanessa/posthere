import os
import re
import json
from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse
from groq import Groq
from services import handle_report_and_match
from database import get_session, save_session

app = Flask(__name__)
groq_client = Groq(api_key=os.environ.get("GROQ_API_KEY"))

# The "No-Nonsense" Prompt
SYSTEM_PROMPT = """
You are the "PostHere Goma Matching Engine". You are NOT a virtual assistant.
Your ONLY goal is to extract data for the Lost & Found database.

STRICT RULES:
1. Never say "I am a large language model" or "I cannot share info".
2. Never suggest social media. The system handles all connections.
3. Be kind but brief. 
4. If FOUND: You MUST ask for the 'drop_off_point' (the specific Police Station address).
5. When details are complete, output this JSON block ONLY:
{"type":"lost/found", "item":"...", "location":"...", "description":"...", "drop_off_point":"...", "unique_detail_1":"..."}

Processing match... The system will now notify any potential owners via automated WhatsApp.
"""

@app.route("/", methods=['GET'])
def index():
    return "PostHere System Active", 200

@app.route("/whatsapp", methods=['POST'])
def whatsapp():
    sender = request.values.get('From', '')
    msg = request.values.get('Body', '').strip()

    # Help Override
    if any(word in msg.lower() for word in ["help", "aide", "stuck"]):
        resp = MessagingResponse()
        resp.message("🆘 *PostHere Goma*\nTo report an item, simply describe it and mention your Quartier. For human help, call +243 000 000.")
        return str(resp)

    # History Management
    history = get_session(sender) or [{"role": "system", "content": SYSTEM_PROMPT}]
    history.append({"role": "user", "content": msg})

    # AI Processing
    try:
        chat = groq_client.chat.completions.create(
            messages=history,
            model="llama-3.3-70b-versatile",
            temperature=0.2 # Very low to prevent AI "chatting"
        )
        ai_msg = chat.choices[0].message.content
    except:
        ai_msg = "System temporarily busy. Please try again."

    # JSON & Match Logic
    json_match = re.search(r'\{.*\}', ai_msg, re.DOTALL)
    if json_match:
        try:
            data = json.loads(json_match.group())
            # This triggers the code in services.py to send the proactive SMS
            rep_id, matches = handle_report_and_match(data, sender)
            
            ai_msg = re.sub(r'\{.*\}', '', ai_msg).strip()
            if matches:
                ai_msg += "\n\n🚨 *MATCH DETECTED!* I have sent a notification to the other party immediately."
            else:
                ai_msg += "\n\n✅ Report filed. You will receive a WhatsApp message the moment a match is found."
        except Exception as e:
            print(f"Logic Error: {e}")

    history.append({"role": "assistant", "content": ai_msg})
    save_session(sender, history[-10:])

    resp = MessagingResponse()
    resp.message(ai_msg)
    return str(resp)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
