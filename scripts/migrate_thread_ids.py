# scripts/migrate_thread_ids.py — run once
"""
Normalize every message document so its thread_id uses the canonical
'user-<user_id>' format. Safe to run multiple times.
"""
from pymongo import MongoClient
from bson import ObjectId
import os

client = MongoClient(os.environ['MONGO_URI'])
db = client[os.environ['MONGO_DB_NAME']]

changed = 0
for doc in db['messages'].find({}):
    tid = doc.get('thread_id') or ''
    uid = doc.get('user_id')

    # Case 1: thread_id is a bare ObjectId string; prefix it.
    if uid and tid and not tid.startswith('user-'):
        # If tid looks like a user id, use user_id
        new_tid = f"user-{uid}"
    # Case 2: no thread_id at all but we have user_id
    elif uid and not tid:
        new_tid = f"user-{uid}"
    else:
        continue

    if new_tid != tid:
        db['messages'].update_one(
            {'_id': doc['_id']},
            {'$set': {'thread_id': new_tid}},
        )
        changed += 1

print(f'Migrated {changed} message(s).')