import sqlite3

def create_database():
    conn = sqlite3.connect('goma_lost_found.db')
    cursor = conn.cursor()
    
    # Drop old table if exists (careful in production!)
    cursor.execute('DROP TABLE IF EXISTS items')
    
    # Updated schema with mediation support
    cursor.execute('''
        CREATE TABLE items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            item_name TEXT,               -- translated english keyword for search
            location TEXT,
            status TEXT,                  -- 'lost' or 'found'
            description TEXT,
            secret1 TEXT,                 -- first exact secret field
            secret2 TEXT,                 -- second exact secret field
            phone_number TEXT,            -- reporter's WhatsApp number
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            match_status TEXT DEFAULT 'open',          -- open | pending_approval | approved | resolved
            claim_code TEXT,                           -- 6-digit code for final verification
            claimed_by_phone TEXT                      -- who claimed it (loser)
        )
    ''')
    
    conn.commit()
    conn.close()
    print("✅ Database schema updated with secure mediation fields!")

if __name__ == "__main__":
    create_database()