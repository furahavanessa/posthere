import os
from twilio.rest import Client
from database import execute_query

# Twilio Setup
client = Client(os.getenv("TWILIO_ACCOUNT_SID"), os.getenv("TWILIO_AUTH_TOKEN"))
TWILIO_NUM = os.getenv("TWILIO_WHATSAPP_NUMBER")

def check_db_for_matches(phone):
    """Checks the database for real results to prevent AI lies."""
    # 1. Get the user's most recent report
    user_item = execute_query(
        "SELECT item_name, status FROM items WHERE phone_number = %s ORDER BY created_at DESC LIMIT 1",
        (phone,), fetch=True
    )
    
    if not user_item:
        return "⚠️ You haven't filed a report yet. Tell me what you lost or found first!"

    name = user_item[0]['item_name']
    looking_for = 'found' if user_item[0]['status'] == 'lost' else 'lost'

    # 2. Check for opposite status in the DB
    match = execute_query(
        "SELECT location, description FROM items WHERE item_name ILIKE %s AND status = %s AND match_status = 'open'",
        (f"%{name}%", looking_for), fetch=True
    )

    if match:
        return f"✅ *YES!* A {name} was reported as {looking_for} in {match[0]['location']}. Please go to the Mairie de Goma to confirm."
    else:
        return f"🔍 *No Match Yet:* I see your report for a {name}, but nobody has reported the other side of it yet. I will text you immediately when they do."

def handle_report_and_match(data, phone):
    """Saves report and alerts the 'other' person if they exist."""
    item_type = data.get('type')
    target_type = 'found' if item_type == 'lost' else 'lost'
    item_name = data['item'].lower().strip()

    # Save to items table
    query = """
        INSERT INTO items (item_name, location, status, description, secret1, phone_number)
        VALUES (%s, %s, %s, %s, %s, %s) RETURNING id
    """
    params = (item_name, data['location'], item_type, data['description'], data['unique_detail_1'], phone)
    res = execute_query(query, params, fetch=True)

    # Search and send PROACTIVE notification to the other person
    matches = execute_query(
        "SELECT phone_number FROM items WHERE item_name ILIKE %s AND status = %s",
        (f"%{item_name}%", target_type), fetch=True
    )

    if matches:
        for m in matches:
            try:
                client.messages.create(
                    from_=TWILIO_NUM,
                    body=f"🚨 *PostHere Alert:* A match for your {item_name} has been found! Please visit the Mairie de Goma.",
                    to=m['phone_number']
                )
            except: pass

    return res[0]['id'] if res else None, matches