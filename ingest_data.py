import sqlite3
import json
from pathlib import Path
import logging

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)

SCRIPT_DIR = Path(__file__).parent.resolve()
DB_PATH = SCRIPT_DIR / "jihs_rag.db"
JSON_FILE = SCRIPT_DIR / "data_clean" / "rag_dataset.json"

def init_db(conn):
    """Reset tabel agar bersih dari data lama"""
    conn.execute("DROP TABLE IF EXISTS chunks")
    conn.execute("""
        CREATE TABLE chunks (
            id TEXT PRIMARY KEY,
            source TEXT,
            section_heading TEXT,
            content TEXT NOT NULL,
            category TEXT DEFAULT 'umum',
            language TEXT DEFAULT 'id',
            is_dummy INTEGER DEFAULT 0
        )
    """)
    conn.commit()

def ingest_data():
    if not Path(JSON_FILE).exists():
        logger.error(f"❌ File tidak ditemukan: {JSON_FILE}")
        return

    with open(JSON_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
    logger.info(f"📦 Loaded {len(data)} entri")

    conn = sqlite3.connect(DB_PATH)
    init_db(conn)  # Clean slate

    inserted = 0
    skipped = 0

    for i, entry in enumerate(data, 1):
        try:
            if not isinstance(entry, dict):
                raise ValueError("Format entry bukan dictionary")

            # Cast eksplisit untuk hindari datatype mismatch
            entry_id = str(entry.get("id", f"chunk_{i}"))
            source = str(entry.get("source", "unknown"))
            section = str(entry.get("section_heading", ""))
            content = str(entry.get("content", ""))
            
            metadata = entry.get("metadata", {}) or {}
            category = str(metadata.get("category", "umum"))
            language = str(metadata.get("language", "id"))
            is_dummy = int(1 if metadata.get("is_dummy") else 0)

            if not content or not entry_id:
                raise ValueError("Missing content atau id")

            conn.execute("""
                INSERT INTO chunks (id, source, section_heading, content, category, language, is_dummy)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (entry_id, source, section, content, category, language, is_dummy))

            inserted += 1

        except Exception as e:
            if skipped == 0:  # Tampilkan hanya error pertama agar log tidak spam
                logger.error(f"❌ Error pada entri #{i}: {e}")
                logger.error(f"   📄 Data problematic: {entry}")
            skipped += 1

    conn.commit()
    count = conn.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]
    
    logger.info(f"\n🎉 Selesai!")
    logger.info(f"   • Inserted: {inserted}")
    logger.info(f"   • Skipped: {skipped}")
    logger.info(f"   • ✅ Total di SQLite: {count}")
    logger.info(f"   • 🗄️ DB Location: {DB_PATH}")
    conn.close()

if __name__ == "__main__":
    ingest_data()