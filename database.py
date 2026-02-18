import os
import psycopg2
import json
from psycopg2.extras import RealDictCursor

DATABASE_URL = os.getenv("DATABASE_URL")

def get_db_connection():
    return psycopg2.connect(
        DATABASE_URL,
        cursor_factory=RealDictCursor,
        sslmode='require'
    )

def execute_query(query, params=(), fetch=False):
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(query, params)
            if fetch:
                result = cur.fetchall()
                return result
            conn.commit()
            return True
    except Exception as e:
        print(f"Database Error: {e}")
        conn.rollback()
        return None
    finally:
        conn.close()

def get_session(phone):
    query = "SELECT history FROM sessions WHERE phone_number = %s"
    res = execute_query(query, (phone,), fetch=True)
    return res[0]['history'] if res else None

def save_session(phone, history):
    query = """
        INSERT INTO sessions (phone_number, history) VALUES (%s, %s)
        ON CONFLICT (phone_number) DO UPDATE SET history = EXCLUDED.history
    """
    execute_query(query, (phone, json.dumps(history)))
