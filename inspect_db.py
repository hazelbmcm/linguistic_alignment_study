import sqlite3

conn = sqlite3.connect("experiment.db")
cursor = conn.cursor()

print("\n--- QUESTION SESSIONS ---")
cursor.execute("SELECT * FROM question_sessions")
rows = cursor.fetchall()

for row in rows:
    print(row)

print(f"\nTotal sessions: {len(rows)}")


print("\n--- MESSAGES ---")
cursor.execute("SELECT * FROM messages")
rows = cursor.fetchall()

for row in rows:
    print(row)

print(f"\nTotal messages: {len(rows)}")

conn.close()