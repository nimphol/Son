import sqlite3

conn = sqlite3.connect("bot_data.db")
for user_id, role, content, when in conn.execute(
    "SELECT user_id, role, content, created_at FROM messages ORDER BY id DESC LIMIT 30"
):
    print(f"[{when}] {user_id} ({role}): {content[:200]}")