import os
from twilio.rest import Client
from database import execute_query
from deep_translator import GoogleTranslator

# Config
client = Client(os.getenv("TWILIO_ACCOUNT_SID"), os.getenv("TWILIO_AUTH_TOKEN"))
TWILIO_NUM = os.getenv("TWILIO_WHATSAPP_NUMBER")

def translate_to_en(text):
    try:
        return GoogleTranslator(source='auto', target='en').translate(text).lower().strip()
    except:
        return text.lower().strip()

def send_alert(phone, text):
    """Bypasses AI to send a direct notification."""
    try:
        client.messages.create(from_=TWILIO_NUM, body=text, to=phone)
    except Exception as e:
        print(f"Notification Error: {e}")

def handle_report_and_match(data, phone):
    item_type = data.get('type')
    target_type = 'found' if item_type == 'lost' else 'lost'
    translated_item = translate_to_en(data['item'])
    drop_off = data.get('drop_off_point', 'The local police post')
    secret = data.get('unique_detail_1', '').lower()

    # 1. Save Report
    save_query = """
        INSERT INTO items (item_name, location, status, description, secret1, phone_number)
        VALUES (%s, %s, %s, %s, %s, %s) RETURNING id
    """
    res = execute_query(save_query, (translated_item, data['location'], item_type, data['description'], secret, phone), fetch=True)
    new_id = res[0]['id'] if res else None

    # 2. Match & Notify (PROACTIVE)
    match_query = """
        SELECT phone_number, secret1 FROM items 
        WHERE item_name ILIKE %s AND status = %s AND match_status = 'open'
    """
    # Look for items with similar names
    potential_matches = execute_query(match_query, (f"%{translated_item}%", target_type), fetch=True)
    
    verified_matches = []
    if potential_matches:
        for m in potential_matches:
            # Check if secrets match or if it's a strong enough keyword match
            if m['secret1'] == secret or len(translated_item) > 4:
                verified_matches.append(m)
                
                # Notify the person already in the DB
                other_phone = m['phone_number']
                if item_type == 'found':
                    msg = f"🚨 *PostHere Alert*: Someone just FOUND an item matching your lost {translated_item}! Go to: {drop_off} to verify your secret: {secret}."
                else:
                    msg = f"🚨 *PostHere Alert*: The owner of the {translated_item} you found has been located! Please ensure the item is safe at: {drop_off}."
                
                send_alert(other_phone, msg)

    return new_id, verified_matches