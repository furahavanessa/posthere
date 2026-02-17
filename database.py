import sqlite3

def init_db():
    # Connect to (or create) the database file
    conn = sqlite3.connect('goma_lost_found.db')
    cursor = conn.cursor()
    
    # We use a single table 'items' to store everything
    # INTEGER PRIMARY KEY AUTOINCREMENT ensures every item has a unique ID number
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            item_name TEXT NOT NULL,      -- e.g., 'Phone', 'Wallet'
            location TEXT NOT NULL,       -- e.g., 'Majengo', 'Himbi'
            status TEXT NOT NULL,         -- 'lost' or 'found'
            description TEXT,             -- General description (e.g., 'Black Tecno')
            secret_details TEXT,          -- THE DETECTIVE PART: (e.g., 'Cracked screen on bottom left')
            image_url TEXT,               -- Link to the WhatsApp photo
            phone_number TEXT,            -- Who reported it?
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    conn.commit()
    conn.close()
    print("✅ GomaBot Database initialized with Detective features!")

if __name__ == "__main__":
    init_db()