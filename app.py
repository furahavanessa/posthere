from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse
from groq import Groq
from services import handle_report_and_match
from database import get_session, save_session
import os, re, json

app = Flask(__name__)
groq_client = Groq(api_key=os.getenv("GROQ_API_KEY"))

@app.route("/whatsapp", methods=['POST'])
def whatsapp():
    phone = request.values.get('From')
    message = request.values.get('Body')
    
    # Manage History
    history = get_session(phone) or [{"role": "system", "content": "You are a Lost & Found assistant for Goma. If a report is complete, provide JSON: {'type':'lost/found','item':'...','location':'...','description':'...','unique_detail_1':'...','unique_detail_2':'...'}"}]
    history.append({"role": "user", "content": message})

    # AI Response
    chat_completion = groq_client.chat.completions.create(
        messages=history, model="llama-3.1-70b-versatile"
    )
    ai_msg = chat_completion.choices[0].message.content
    
    # Check for JSON in AI response
    json_match = re.search(r'\{.*\}', ai_msg, re.DOTALL)
    if json_match:
        try:
            report_data = json.loads(json_match.group())
            rep_id, matches = handle_report_and_match(report_data, phone)
            ai_msg = re.sub(r'\{.*\}', '', ai_msg) # Clean JSON out of text
            ai_msg += "\n\n✅ Registered! We are looking for matches."
            if matches:
                ai_msg += "\n\n🚨 Good news! We found a potential match. Please visit the Mairie de Goma."
        except: pass

    history.append({"role": "assistant", "content": ai_msg})
    save_session(phone, history[-10:]) # Keep last 10 messages

    resp = MessagingResponse()
    resp.message(ai_msg)
    return str(resp)

if __name__ == "__main__":
    app.run(port=5000)
