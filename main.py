# main.py — PostgreSQL version for Supabase / Neon

import os
import psycopg2
from psycopg2.extras import RealDictCursor
from deep_translator import GoogleTranslator
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

def get_db_connection():
    return psycopg2.connect(
        DATABASE_URL,
        cursor_factory=RealDictCursor,
        sslmode='require'   # Supabase requires SSL
    )

def translate_to_key(text):
    try:
        translated = GoogleTranslator(source='auto', target='en').translate(text)
        return (translated or text).lower().strip()
    except:
        return text.lower().strip()

def save_report(data, phone, status):
    conn = get_db_connection()
    cur = conn.cursor()

    key_name = translate_to_key(data['item'])

    cur.execute("""
        INSERT INTO items (
            item_name, location, status, description,
            secret1, secret2, phone_number
        ) VALUES (%s, %s, %s, %s, %s, %s, %s)
        RETURNING id
    """, (
        key_name,
        data['location'],
        status,
        data['specs'],
        data['secret1'].strip().lower(),
        data['secret2'].strip().lower(),
        phone
    ))

    inserted_id = cur.fetchone()['id']
    conn.commit()
    cur.close()
    conn.close()
    return inserted_id

def find_secure_matches(item_name, location, secret1, secret2, target_status):
    conn = get_db_connection()
    cur = conn.cursor()

    key_search = translate_to_key(item_name)
    words = [w for w in key_search.split() if len(w) >= 3]
    if not words:
        conn.close()
        return []

    conditions = " AND ".join("item_name LIKE %s" for _ in words)
    params = [f"%{w}%" for w in words]
    params.extend([f"%{location.strip().lower()}%", target_status, 'open'])

    query = f"""
        SELECT id, phone_number, description, item_name, secret1, secret2
        FROM items
        WHERE {conditions}
          AND location LIKE %s
          AND status = %s
          AND match_status = %s
    """

    cur.execute(query, params)
    results = cur.fetchall()
    conn.close()

    verified = []
    s1 = secret1.strip().lower()
    s2 = secret2.strip().lower()

    for row in results:
        if row['secret1'] == s1 and row['secret2'] == s2:
            verified.append({
                'id': row['id'],
                'phone': row['phone_number'],
                'description': row['description'],
                'item_name': row['item_name']
            })

    return verified