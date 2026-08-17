import sqlite3

conn = sqlite3.connect('database/comments.db')
cursor = conn.execute('''
    SELECT author, message, created_time 
    FROM comments 
    WHERE message LIKE "%ชุดกันหนาว%" 
    ORDER BY created_time DESC
''')

print("Comments matching 'ชุดกันหนาว':\n")
results = cursor.fetchall()
if results:
    for i, row in enumerate(results, 1):
        print(f"{i}. [{row[0]}] {row[1]}")
        print(f"   Time: {row[2]}\n")
else:
    print("No comments found with 'ชุดกันหนาว'")

conn.close()
