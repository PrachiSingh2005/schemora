import sqlite3
import os
import logging

logger = logging.getLogger(__name__)

def migrate():
    db_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "schemora_dev.db"))
    if not os.path.exists(db_path):
        return

    conn = sqlite3.connect(db_path)

    # 1. Migrate knowledge_chunks table
    cur = conn.execute("PRAGMA table_info(knowledge_chunks)")
    kc_cols = {row[1] for row in cur.fetchall()}
    kc_new_cols = [
        ("source_name", "TEXT"),
        ("official_scheme_url", "TEXT"),
        ("official_portal_url", "TEXT"),
    ]
    for col_name, col_type in kc_new_cols:
        if col_name not in kc_cols:
            try:
                conn.execute(f"ALTER TABLE knowledge_chunks ADD COLUMN {col_name} {col_type}")
                logger.info(f"Added column knowledge_chunks.{col_name}")
            except Exception as e:
                logger.warning(f"Error adding column knowledge_chunks.{col_name}: {e}")

    # 2. Migrate schemes table
    cur2 = conn.execute("PRAGMA table_info(schemes)")
    s_cols = {row[1] for row in cur2.fetchall()}
    s_new_cols = [
        ("source_url", "TEXT"),
        ("source_name", "TEXT DEFAULT 'Official Portal'"),
        ("official_scheme_url", "TEXT"),
        ("application_url", "TEXT"),
        ("official_portal_url", "TEXT"),
    ]
    for col_name, col_type in s_new_cols:
        if col_name not in s_cols:
            try:
                conn.execute(f"ALTER TABLE schemes ADD COLUMN {col_name} {col_type}")
                logger.info(f"Added column schemes.{col_name}")
            except Exception as e:
                logger.warning(f"Error adding column schemes.{col_name}: {e}")

    conn.commit()
    conn.close()

if __name__ == "__main__":
    migrate()
