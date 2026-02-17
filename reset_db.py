import sqlite3

conn = sqlite3.connect('goma_lost_found.db')
cursor = conn.cursor()

# Drop the old table if it exists
cursor.execute('DROP TABLE IF EXISTS items')

# Create the new table with ALL columns
cursor.execute('''
    CREATE TABLE items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        item_name TEXT,
        location TEXT,
        status TEXT,
        description TEXT,
        secret_details TEXT,
        image_url TEXT,
        phone_number TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
''')

conn.commit()
conn.close()
print("✅ Database refreshed! All columns are now present.")