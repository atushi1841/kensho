#!/usr/bin/env python3
import sqlite3
DB='/home/atushi/.hermes/kanban/boards/kensho-ai-team/kanban.db'
c=sqlite3.connect(DB)
for s in ['todo','blocked']:
    print("=== status",s,"===")
    for r in c.execute("select id,title,assignee,priority,status from tasks where status=?",(s,)):
        print(r)
print("=== recent done (last 15) ===")
for r in c.execute("select id,title,assignee,status from tasks where status='done' order by completed_at desc limit 15"):
    print(r)
