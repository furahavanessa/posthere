import os
from twilio.rest import Client
from database import execute_query

# Initialize Twilio Client
TWILIO_SID = os.environ.get("TWILIO_ACCOUNT_SID")
TWILIO_TOKEN = os.environ.get("TWILIO_AUTH_TOKEN")
TWILIO_NUM = os.environ.get("TWILIO_WHATSAPP_NUMBER")
client = Client(TWILIO_SID, TWILIO_TOKEN)

def check_db_for_matches(phone):
    """Checks real DB rows to prevent AI hallucinations."""
    user_report = execute_query(
        "SELECT item_name, status FROM items WHERE phone_number = %s ORDER BY created_at DESC LIMIT 1",
        (phone,), fetch=True
    )
    
    if not user_report:
        return "I don't see an active report for this number. Please tell me what you lost or found."

    name = user_report[0]['item_name']
    target_status = 'found' if user_report[0]['status'] == 'lost' else 'lost'

    # Real Search
    match = execute_query(
        "SELECT location, drop_off_point FROM items WHERE item_name ILIKE %s AND status = %s AND match_status = 'open' LIMIT 1",
        (f"%{name}%", target_status), fetch=True
    )

    if match:
        location = match[0].get('location', 'Goma')
        drop_off = match[0].get('drop_off_point', 'the police post')
        return f"✅ *Good news!* I found a matching {name} in our database reported at {location}. It is kept at: {drop_off}."
    
    return f"🔍 I am still searching for a match for your {name}. I will alert you the second it is reported."

def handle_report_and_match(data, phone):
    """Saves report and proactively notifies the other party."""
    item_type = data.get('type')
    target_type = 'found' if item_type == 'lost' else 'lost'
    item_name = data.get('item', '').lower().strip()
    drop_off = data.get('drop_off_point', 'Not Specified')

    # 1. Save to Database
    query = """
        INSERT INTO items (item_name, location, status, description, secret1, drop_off_point, phone_number)
        VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING id
    """
    params = (item_name, data.get('location'), item_type, data.get('description'), data.get('unique_detail_1'), drop_off, phone)
    res = execute_query(query, params, fetch=True)

    # 2. Proactive Search & Alert
    matches = execute_query(
        "SELECT phone_number FROM items WHERE item_name ILIKE %s AND status = %s AND match_status = 'open'",
        (f"%{item_name}%", target_type), fetch=True
    )

    if matches:
        for m in matches:
            other_phone = m['phone_number']
            # Ensure prefix is correct
            if not other_phone.startswith("whatsapp:"):
                other_phone = f"whatsapp:{other_phone}"
            
            try:
                client.messages.create(
                    from_=TWILIO_NUM,
                    body=f"🚨 *PostHere Alert:* A match for your {item_name} has been found! Please visit your designated police station.",
                    to=other_phone
                )
            except Exception as e:
                print(f"Proactive Alert Failed: {e}")

    return res[0]['id'] if res else None, matches