import os
from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse
from services import handle_simple_report, check_matches_and_notify
from database import execute_query

app = Flask(__name__)

@app.route("/whatsapp", methods=['POST'])
def whatsapp():
    phone = request.values.get('From', '')
    message = request.values.get('Body', '').strip().lower()
    
    # 1. Check user's current "Step" in the process
    # We use a simple table or session to track their progress
    user_session = execute_query("SELECT step, data FROM sessions WHERE phone_number = %s", (phone,), fetch=True)
    
    resp = MessagingResponse()
    
    if not user_session or message in ["reset", "start", "hello", "hi"]:
        execute_query("DELETE FROM sessions WHERE phone_number = %s", (phone,))
        execute_query("INSERT INTO sessions (phone_number, step, data) VALUES (%s, %s, %s)", (phone, 1, '{}'))
        reply = "Welcome to PostHere Goma. 📍\n\nDid you **LOST** an item or **FOUND** an item? (Reply with one word)"
        resp.message(reply)
        return str(resp)

    step = user_session[0]['step']
    data = json.loads(user_session[0]['data']) if user_session[0]['data'] else {}

    # 2. THE FLOW LOGIC
    if step == 1: # Capture Type
        if "lost" in message or "found" in message:
            data['type'] = "lost" if "lost" in message else "found"
            next_msg = "What is the name of the item? (e.g., Samsung S10, Brown Wallet)"
            execute_query("UPDATE sessions SET step = 2, data = %s WHERE phone_number = %s", (json.dumps(data), phone))
        else:
            next_msg = "Please reply with either 'LOST' or 'FOUND'."
            
    elif step == 2: # Capture Item Name
        data['item'] = message
        next_msg = "In which Quartier (Neighborhood) of Goma? (e.g., Birere, Mabanga, Virunga)"
        execute_query("UPDATE sessions SET step = 3, data = %s WHERE phone_number = %s", (json.dumps(data), phone))

    elif step == 3: # Capture Location
        data['location'] = message
        next_msg = "Provide a unique secret detail (e.g., specific lock screen photo, a crack on the left side)."
        execute_query("UPDATE sessions SET step = 4, data = %s WHERE phone_number = %s", (json.dumps(data), phone))

    elif step == 4: # Finalize and Search
        data['secret'] = message
        # Save to main items table
        handle_simple_report(data, phone)
        
        # Search for matches
        match_found = check_matches_and_notify(data, phone)
        
        if match_found:
            next_msg = "✅ DONE! We found a potential match in our database! Please head to the Mairie de Goma police post for verification."
        else:
            next_msg = "✅ Report Filed. We are searching... We will WhatsApp you the moment a match is reported."
            
        # Reset session so they can start over later
        execute_query("DELETE FROM sessions WHERE phone_number = %s", (phone,))

    resp.message(next_msg)
    return str(resp)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)