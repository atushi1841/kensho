import sqlite3
import sys

conn = sqlite3.connect('/home/atushi/.hermes/kanban/boards/kensho-ai-team/kanban.db')
c = conn.cursor()
c.execute('SELECT id, title, status, last_failure_error FROM tasks LIMIT 20')
rows = c.fetchall()
for r in rows:
    print(r)

conn.close()