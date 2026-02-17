import sqlite3

def view_all_items():
    conn = sqlite3.connect('goma_lost_found.db')
    cursor = conn.cursor()
    
    # Query all columns
    cursor.execute("SELECT * FROM items")
    rows = cursor.fetchall()
    
    # Get column names to make it readable
    column_names = [description[0] for description in cursor.description]
    print(f"{' | '.join(column_names)}")
    print("-" * 100)
    
    for row in rows:
        print(row)
    
    conn.close()

if __name__ == "__main__":
    print("--- Current Items in Database ---")
    view_all_items()