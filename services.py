import json
import re
from deep_translator import GoogleTranslator
from database import execute_query

def translate_to_key(text):
    try:
        translated = GoogleTranslator(source='auto', target='en').translate(text)
        return (translated or text).lower().strip()
    except:
        return text.lower().strip()

def handle_report_and_match(data, phone):
    """Saves the report and immediately looks for a match."""
    status = data.get('type')
    target_status = 'found' if status == 'lost' else 'lost'
    key_name = translate_to_key(data['item'])
    
    # 1. Save to DB
    query = """
        INSERT INTO items (item_name, location, status, description, secret1, secret2, phone_number)
        VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING id
    """
    params = (key_name, data['location'], status, data['description'], 
              data['unique_detail_1'].lower(), data['unique_detail_2'].lower(), phone)
    
    res = execute_query(query, params, fetch=True)
    report_id = res[0]['id'] if res else None

    # 2. Match Logic
    words = [w for w in key_name.split() if len(w) >= 3]
    if not words: return report_id, []

    conditions = " AND ".join(["item_name LIKE %s"] * len(words))
    sql_params = [f"%{w}%" for w in words] + [f"%{data['location']}%", target_status, 'open']
    
    match_query = f"""
        SELECT phone_number, secret1, secret2 FROM items 
        WHERE {conditions} AND location LIKE %s AND status = %s AND match_status = %s
    """
    
    potential_matches = execute_query(match_query, sql_params, fetch=True)
    verified = [m for m in potential_matches if m['secret1'] == data['unique_detail_1'].lower()]
    
    return report_id, verified
