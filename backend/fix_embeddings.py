"""Fix existing embeddings: add chatbot_id/tenant_id from DataSource"""
import os
import sys
from dotenv import load_dotenv
load_dotenv()

import psycopg2

DATABASE_URL = os.environ.get('DATABASE_URL')
if not DATABASE_URL:
    print("ERROR: DATABASE_URL not set")
    sys.exit(1)

conn = psycopg2.connect(DATABASE_URL)
cur = conn.cursor()

# Count embeddings with NULL chatbot_id
cur.execute("SELECT COUNT(*) FROM document_embeddings WHERE chatbot_id IS NULL")
null_count = cur.fetchone()[0]
print(f"Embeddings with NULL chatbot_id: {null_count}")

if null_count > 0:
    # Update embeddings by joining with data_sources via doc_id
    # The doc_id in document_embeddings matches meta_data->>'doc_id' in data_sources
    cur.execute("""
        UPDATE document_embeddings de
        SET chatbot_id = ds.chatbot_id,
            tenant_id = ds.tenant_id
        FROM data_sources ds
        WHERE de.chatbot_id IS NULL
        AND de.meta_data->>'doc_id' = ds.meta_data->>'doc_id'
        AND ds.chatbot_id IS NOT NULL
    """)
    updated = cur.rowcount
    conn.commit()
    print(f"Updated {updated} embeddings with chatbot_id from data_sources")

    # Check remaining nulls
    cur.execute("SELECT COUNT(*) FROM document_embeddings WHERE chatbot_id IS NULL")
    remaining = cur.fetchone()[0]
    print(f"Remaining embeddings with NULL chatbot_id: {remaining}")
else:
    print("No embeddings need fixing")

# Show summary
cur.execute("""
    SELECT chatbot_id, COUNT(*) as cnt 
    FROM document_embeddings 
    GROUP BY chatbot_id 
    ORDER BY chatbot_id
""")
print("\nEmbeddings by chatbot_id:")
for row in cur.fetchall():
    print(f"  chatbot_id={row[0]}: {row[1]} embeddings")

cur.close()
conn.close()
print("\nDone!")
