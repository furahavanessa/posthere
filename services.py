import os
from twilio.rest import Client
from database import execute_query
from deep_translator import GoogleTranslator

client = Client(os.getenv("TWILIO_ACCOUNT_SID"), os.getenv("TWILIO_AUTH_TOKEN"))
TWILIO_NUM = os.getenv("TWILIO_WHATSAPP_NUMBER")

def check_db_for_matches(phone):
    """Bypasses AI to look at real database rows."""
    # Find user's last report
    last_item = execute_query(
        "SELECT item_name, status FROM items WHERE phone_number = %s ORDER BY created_at DESC LIMIT 1",
        (phone,), fetch=True
    )
    
    if not last_item:
        return "❌ You haven't filed a report yet. Please tell me what you lost or found."
    
    name = last_item[0]['item_name']
    target = 'found' if last_item[0]['status'] == 'lost' else 'lost'
    
    # Check for real matches
    match = execute_query(
        "SELECT location, description FROM items WHERE item_name ILIKE %s AND status = %s AND match_status = 'open' LIMIT 1",
        (f"%{name}%", target), fetch=True
    )
    
    if match:
        return f"🚨 *REAL MATCH FOUND!* We found a {name} reported in {match[0]['location']}. Description: {match[0]['description']}. Please visit the Mairie de Goma."
    
    return f"🔍 *Searching...* I see your report for a {name}, but no one has found it yet. I will message you the second it is reported."

def handle_report_and_match(data, phone):
    item_type = data.get('type')
    target_type = 'found' if item_type == 'lost' else 'lost'
    item_name = data['item'].lower().strip()
    
    # Save to DB
    query = """
        INSERT INTO items (item_name, location, status, description, secret1, phone_number)
        VALUES (%s, %s, %s, %s, %s, %s) RETURNING id
    """
    res = execute_query(query, (item_name, data['location'], item_type, data['description'], data['unique_detail_1'], phone), fetch=True)
    
    # Proactive Search
    matches = execute_query(
        "SELECT phone_number FROM items WHERE item_name ILIKE %s AND status = %s",
        (f"%{item_name}%", target_type), fetch=True
    )
    
    if matches:
        for m in matches:
            try:
                client.messages.create(
                    from_=TWILIO_NUM,
                    body=f"🚨 *POSTHERE ALERT*: A match for your {item_name} has been reported! Go to the police post for verification.",
                    to=m['phone_number']
                )
            except: pass
            
    return res[0]['id'] if res else None, matches