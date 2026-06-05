import os
from dotenv import load_dotenv
load_dotenv('.env')
import psycopg2

conn = psycopg2.connect(os.environ['DATABASE_URL'])
cur = conn.cursor()
cur.execute("""
    SELECT column_name FROM information_schema.columns
    WHERE table_name = 'users'
    ORDER BY ordinal_position
""")
cols = [r[0] for r in cur.fetchall()]
print('Current users table columns:')
for c in cols:
    print(f'  {c}')

# Check if reset_token column already exists
if 'reset_token' in cols:
    print('\n[SKIP] reset_token column already exists')
else:
    print('\n[ADD] Adding reset_token and reset_token_expires columns...')
    cur.execute('ALTER TABLE users ADD COLUMN IF NOT EXISTS reset_token VARCHAR(100) UNIQUE')
    cur.execute('ALTER TABLE users ADD COLUMN IF NOT EXISTS reset_token_expires TIMESTAMP')
    conn.commit()
    print('[OK] Columns added successfully')

# Verify
cur.execute("""
    SELECT column_name FROM information_schema.columns
    WHERE table_name = 'users' AND column_name IN ('reset_token', 'reset_token_expires')
    ORDER BY ordinal_position
""")
new_cols = [r[0] for r in cur.fetchall()]
print('\nNew columns:')
for c in new_cols:
    print(f'  {c}')

cur.close()
conn.close()
