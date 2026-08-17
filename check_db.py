import sqlite3

conn = sqlite3.connect('database/comments.db')
cursor = conn.execute('''
    SELECT author, message, created_time 
    FROM comments 
    ORDER BY created_time DESC 
    LIMIT 20
''')

print("Latest 20 comments (newest first):\n")
print("=" * 80)
for i, row in enumerate(cursor.fetchall(), 1):
    author, message, created_time = row
    display_msg = message[:60] + "..." if len(message) > 60 else message
    print(f"{i}. [{author}] {display_msg}")
    print(f"   Time: {created_time}\n")

conn.close()
