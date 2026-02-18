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

# Strict Prompt: Professional, Kind, and Action-Oriented
SYSTEM_PROMPT = """
You are 'PostHere Goma', the official city system for lost and found items.

CORE RULES:
1. **Persona**: Be supportive and kind ("We are here to help") but move directly to data collection.
2. **No AI Talk**: Do not apologize for being a virtual assistant. Do not explain your technical limitations.
3. **Data Collection**: 
   - If LOST: Collect item name, quartier, description, and one unique secret detail.
   - If FOUND: Collect item name, quartier, description, and the MANDATORY 'drop_off_point' (the specific police station or public office where they left the item).
4. **Assistance**: If a user is confused, reassure them and tell them you are checking the official database.

OUTPUT:
Always provide a JSON block at the end when a report is complete:
{"type":"lost/found", "item":"...", "location":"...", "description":"...", "drop_off_point":"...", "unique_detail_1":"..."}
"""

@app.route("/", methods=['GET'])
def index():
    return "PostHere Goma is Live and Running.", 200

@app.route("/whatsapp", methods=['POST'])
def whatsapp():
    sender_phone = request.values.get('From', '')
    user_msg = request.values.get('Body', '').strip()
    user_msg_lower = user_msg.lower()

    # --- 1. EMERGENCY HELP OVERRIDE ---
    # Catching users who are stuck before the AI processes the message
    help_keywords = ["help", "aide", "stuck", "bloqué", "human", "problème"]
    if any(k in user_msg_lower for k in help_keywords):
        resp = MessagingResponse()
        resp.message(
            "🆘 *PostHere Goma Support*\n\n"
            "If you are having trouble:\n"
            "1. State clearly if you 'lost' or 'found' something.\n"
            "2. Give the neighborhood (Quartier) name.\n"
            "3. For human assistance, visit Goma City Hall (Mairie) or call our office at +243 XXX XXX XXX."
        )
        return str(resp)

    # --- 2. CONVERSATION HISTORY ---
    try:
        session_data = get_session(sender_phone)
        history = session_data if session_data else [{"role": "system", "content": SYSTEM_PROMPT}]
    except:
        history = [{"role": "system", "content": SYSTEM_PROMPT}]
    
    history.append({"role": "user", "content": user_msg})

    # --- 3. AI PROCESSING (GROQ) ---
    try:
        chat_completion = groq_client.chat.completions.create(
            messages=history,
            model="llama-3.3-70b-versatile",
            temperature=0.4 # Low temperature for consistency
        )
        ai_msg = chat_completion.choices[0].message.content
    except Exception as e:
        print(f"Groq Error: {e}")
        ai_msg = "I am sorry, our system is currently busy. Please try messaging again in a minute."

    # --- 4. JSON EXTRACTION & PROACTIVE MATCHING ---
    json_match = re.search(r'\{.*\}', ai_msg, re.DOTALL)
    if json_match:
        try:
            report_data = json.loads(json_match.group())
            
            # This function in services.py handles saving AND notifying other users
            rep_id, matches = handle_report_and_match(report_data, sender_phone)
            
            # Clean AI message for display
            ai_msg = re.sub(r'\{.*\}', '', ai_msg).strip()
            ai_msg += "\n\n✅ *Official Report Registered.* I am cross-referencing our database now."
            
            if matches:
                ai_msg += "\n\n🚨 *MATCH FOUND!* We have notified the other party. Please follow the instructions provided to retrieve/verify the item."
        except Exception as e:
            print(f"Data Processing Error: {e}")

    # --- 5. SAVE & RESPOND ---
    history.append({"role": "assistant", "content": ai_msg})
    save_session(sender_phone, history[-12:]) # Keep context reasonably short

    resp = MessagingResponse()
    resp.message(ai_msg)
    return str(resp)

if __name__ == "__main__":
    # Render Port Binding
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
