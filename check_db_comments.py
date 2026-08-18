import sqlite3

conn = sqlite3.connect('database/comments.db')
cursor = conn.cursor()

cursor.execute('''
    SELECT id, tier, author, message, created_time 
    FROM comments 
    WHERE post_url = 'https://www.facebook.com/groups/2965724366922893/permalink/2972275236267806'
    ORDER BY created_time DESC
''')

rows = cursor.fetchall()
print(f'Total comments in database: {len(rows)}\n')

for row in rows:
    comment_id, tier, author, message, created_time = row
    message_short = message[:40] if message else ''
    print(f'T{tier} | {author[:25]:25} | {message_short:40} | {comment_id}')

conn.close()
