import os
import json
from twilio.rest import Client
from database import execute_query

client = Client(os.getenv("TWILIO_ACCOUNT_SID"), os.getenv("TWILIO_AUTH_TOKEN"))
TWILIO_NUM = os.getenv("TWILIO_WHATSAPP_NUMBER")

def handle_simple_report(data, phone):
    """Saves the structured data directly to the database."""
    query = """
        INSERT INTO items (item_name, location, status, description, secret1, phone_number)
        VALUES (%s, %s, %s, %s, %s, %s)
    """
    execute_query(query, (data['item'], data['location'], data['type'], "Standard Report", data['secret'], phone))

def check_matches_and_notify(data, phone):
    """Checks for matches and sends outbound WhatsApps."""
    target_type = "found" if data['type'] == "lost" else "lost"
    
    # Simple Database Search
    query = """
        SELECT phone_number FROM items 
        WHERE item_name ILIKE %s AND status = %s AND match_status = 'open'
    """
    matches = execute_query(query, (f"%{data['item']}%", target_type), fetch=True)
    
    if matches:
        for m in matches:
            other_user = m['phone_number']
            # Notify the person who was already in the database
            try:
                client.messages.create(
                    from_=TWILIO_NUM,
                    body=f"🚨 PostHere Alert: A match for your {data['item']} has been reported! Go to the Mairie de Goma.",
                    to=other_user
                )
            except:
                pass
        return True
    return False