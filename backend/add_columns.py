import os
from dotenv import load_dotenv
load_dotenv()
import psycopg2

conn = psycopg2.connect(os.environ.get('DATABASE_URL'))
cur = conn.cursor()

# Check existing columns
cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name='ai_models'")
existing = [r[0] for r in cur.fetchall()]
print(f"Existing columns: {existing}")

if 'temperature' not in existing:
    cur.execute("ALTER TABLE ai_models ADD COLUMN temperature FLOAT DEFAULT 0.7")
    print("Added temperature column")

if 'top_k' not in existing:
    cur.execute("ALTER TABLE ai_models ADD COLUMN top_k INTEGER DEFAULT 10")
    print("Added top_k column")

conn.commit()
cur.close()
conn.close()
print("Done!")
