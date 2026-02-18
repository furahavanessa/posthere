import os
import json
import re
from deep_translator import GoogleTranslator
from database import execute_query
from twilio.rest import Client

# Twilio Config
TWILIO_SID = os.environ.get("TWILIO_ACCOUNT_SID")
TWILIO_TOKEN = os.environ.get("TWILIO_AUTH_TOKEN")
TWILIO_NUM = os.environ.get("TWILIO_WHATSAPP_NUMBER")
client = Client(TWILIO_SID, TWILIO_TOKEN)

def translate_to_key(text):
    try:
        translated = GoogleTranslator(source='auto', target='en').translate(text)
        return (translated or text).lower().strip()
    except:
        return text.lower().strip()

def notify_user(phone, message):
    """Sends a proactive WhatsApp message to a user."""
    try:
        client.messages.create(
            from_=TWILIO_NUM,
            body=message,
            to=phone
        )
        print(f"Notification sent to {phone}")
    except Exception as e:
        print(f"Twilio Notification Error: {e}")

def handle_report_and_match(data, phone):
    """Saves report and alerts both parties if a match is found."""
    status = data.get('type') # 'lost' or 'found'
    target_status = 'found' if status == 'lost' else 'lost'
    key_name = translate_to_key(data['item'])
    
    # 1. Save the new report to the database
    # We store the 'location' (where it happened) and 'drop_off' (where the item is now)
    query = """
        INSERT INTO items (item_name, location, status, description, secret1, phone_number)
        VALUES (%s, %s, %s, %s, %s, %s) RETURNING id
    """
    params = (
        key_name, 
        data.get('location'), 
        status, 
        f"{data.get('description')} | Drop-off: {data.get('drop_off_point')}", 
        data.get('unique_detail_1', '').lower().strip(), 
        phone
    )
    
    res = execute_query(query, params, fetch=True)
    report_id = res[0]['id'] if res else None

    # 2. Search for Matches
    # We use ILIKE for case-insensitive matching
    words = [w for w in key_name.split() if len(w) >= 3]
    if not words:
        return report_id, []

    conditions = " OR ".join(["item_name ILIKE %s"] * len(words))
    sql_params = [f"%{w}%" for w in words] + [target_status, 'open']
    
    match_query = f"""
        SELECT id, phone_number, secret1, description FROM items 
        WHERE ({conditions}) AND status = %s AND match_status = %s
    """
    
    potential_matches = execute_query(match_query, sql_params, fetch=True)
    
    verified_matches = []
    user_secret = data.get('unique_detail_1', '').lower().strip()

    for match in potential_matches:
        # Cross-verify secrets
        if match['secret1'] == user_secret:
            verified_matches.append(match)
            
            # 3. NOTIFY THE OTHER PERSON
            other_phone = match['phone_number']
            if status == 'found':
                # You found it, notify the person who lost it
                msg = (f"🚨 PostHere Goma: Great news! Someone found an item matching your report. "
                       f"It has been taken to: {data.get('drop_off_point')}. "
                       f"Please go there to verify and claim it.")
            else:
                # You lost it, but it's already in the DB as found
                msg = (f"🚨 PostHere Goma: An item matching your description was previously reported! "
                       f"Check at the police post mentioned in your recent chat.")
            
            notify_user(other_phone, msg)

    return report_id, verified_matches
