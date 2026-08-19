import sqlite3

conn = sqlite3.connect('database/comments.db')
cursor = conn.cursor()

cursor.execute('SELECT COUNT(*) FROM comments')
total = cursor.fetchone()[0]
print(f'Total comments: {total}')

cursor.execute('SELECT id, author, created_time FROM comments ORDER BY created_time DESC LIMIT 10')
print('\nLast 10 comments:')
for row in cursor.fetchall():
    print(f'  ID: {row[0]}, Author: {row[1]}, Time: {row[2]}')

conn.close()
