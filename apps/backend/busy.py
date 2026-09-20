"""Is the box in the middle of something?

Exits 1 when a job is queued or running, 0 when the queue is empty. The deploy
script asks before restarting the worker, because a restart mid-song throws the
song away — which is exactly what happened on 2026-09-20 to a song that was
half made.
"""
import os
import sys

import config
import db
import jobs

S = config.settings()
conn = db.connect(os.path.join(S.data_dir, "app.db"))
depth = jobs.queue_depth(conn)
busy = depth["queued"] + depth["running"]
print(f"{busy} job(s) in the queue" if busy else "queue empty")
sys.exit(1 if busy else 0)
