import sqlite3
import sys
from pathlib import Path

DB_PATH = Path("jihs_rag.db")

def inspect_db(mode="summary", keyword=None, limit=5):
    if not DB_PATH.exists():
        print(f"❌ Database tidak ditemukan: {DB_PATH.absolute()}")
        return
    
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    
    # 1. List semua tabel
    tables = [t['name'] for t in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
    print(f"📦 Database: {DB_PATH.absolute()}")
    print(f"📋 Tabel yang ada: {tables}\n")
    
    if 'chunks' not in tables:
        print("❌ Tabel 'chunks' tidak ditemukan. Jalankan ingest_sqlite.py dulu!")
        conn.close()
        return
    
    # 2. Statistik dasar
    total = conn.execute("SELECT COUNT(*) as c FROM chunks").fetchone()['c']
    print(f"📊 Total baris di 'chunks': {total}")
    
    if total == 0:
        print("⚠️ Tabel kosong! Data belum di-ingest.")
        conn.close()
        return
    
    # 3. Mode: summary / preview / search
    if mode == "search" and keyword:
        print(f"\n🔍 Search keyword: '{keyword}'")
        results = conn.execute("""
            SELECT id, source, section_heading, length(content) as content_len
            FROM chunks 
            WHERE content LIKE ? OR section_heading LIKE ?
            LIMIT ?
        """, (f"%{keyword}%", f"%{keyword}%", limit)).fetchall()
        
        if not results:
            print("   ⚠️ Tidak ada hasil.")
        else:
            for i, row in enumerate(results, 1):
                print(f"\n   [{i}] ID: {row['id']}")
                print(f"       Source: {row['source']}")
                print(f"       Section: {row['section_heading']}")
                print(f"       Content length: {row['content_len']} chars")
    
    elif mode == "preview":
        print(f"\n📋 Preview {limit} baris pertama:")
        results = conn.execute("""
            SELECT id, source, section_heading, content 
            FROM chunks LIMIT ?
        """, (limit,)).fetchall()
        
        for i, row in enumerate(results, 1):
            print(f"\n   [{i}] ID: {row['id']}")
            print(f"       Source: {row['source']}")
            print(f"       Section: {row['section_heading']}")
            content = row['content'][:200] + "..." if len(row['content']) > 200 else row['content']
            print(f"       Content: {content}")
    
    else:  # summary mode
        # Statistik kategori
        cats = conn.execute("SELECT category, COUNT(*) as c FROM chunks GROUP BY category").fetchall()
        print(f"\n📂 Distribusi kategori:")
        for cat in cats:
            print(f"   • {cat['category']}: {cat['c']}")
        
        # Cek dummy data
        dummy_count = conn.execute("SELECT COUNT(*) as c FROM chunks WHERE is_dummy = 1").fetchone()['c']
        print(f"\n🎭 Data dummy: {dummy_count} / {total}")
        
        # Sample ID
        sample_ids = conn.execute("SELECT id FROM chunks LIMIT 3").fetchall()
        print(f"\n🏷️  Sample IDs: {[s['id'] for s in sample_ids]}")
    
    conn.close()
    print("\n" + "="*60)

if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "summary"
    keyword = sys.argv[2] if len(sys.argv) > 2 else None
    inspect_db(mode=mode, keyword=keyword)