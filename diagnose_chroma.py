import chromadb
import os
from pathlib import Path

def diagnose():
    print("🔧 ChromaDB Diagnostic Tool")
    print("=" * 60)
    
    # 1. Cek folder chroma_db
    db_path = Path("./chroma_db")
    print(f"\n1. 📁 Folder chroma_db: {db_path.absolute()}")
    if db_path.exists():
        files = list(db_path.rglob("*"))
        print(f"   ✅ Folder exists, berisi {len(files)} file/folder:")
        for f in files[:10]:  # Tampilkan 10 pertama
            print(f"      - {f.relative_to(db_path)}")
    else:
        print(f"   ❌ Folder tidak ditemukan!")
        return
    
    # 2. Cek collections yang tersedia
    print(f"\n2. 📦 Collections dalam database:")
    try:
        client = chromadb.PersistentClient(path=str(db_path))
        collections = client.list_collections()
        
        if not collections:
            print("   ⚠️ Tidak ada collection sama sekali!")
        else:
            for col in collections:
                count = col.count()
                print(f"   ✅ '{col.name}' → {count} dokumen")
    except Exception as e:
        print(f"   ❌ Error: {e}")
        return
    
    # 3. Cek collection spesifik yang dipakai main.py
    COLLECTION_NAME = "jihs_knowledge"  # Sesuaikan dengan config kamu
    print(f"\n3. 🔎 Cek collection '{COLLECTION_NAME}':")
    
    try:
        collection = client.get_collection(name=COLLECTION_NAME)
        count = collection.count()
        print(f"   ✅ Collection ditemukan, total dokumen: {count}")
        
        if count > 0:
            # Peek sample
            peek = collection.peek(limit=2, include=["documents", "metadatas"])
            print(f"\n   📋 Sample dokumen:")
            for i, (doc, meta) in enumerate(zip(peek['documents'], peek['metadatas']), 1):
                print(f"      [{i}] Section: {meta.get('section', 'N/A')}")
                print(f"          Content: {doc[:150]}...")
        else:
            print(f"   ⚠️ Collection ada tapi KOSONG!")
            print(f"   💡 Kemungkinan: ingest_chroma.py gagal atau pakai collection name berbeda")
            
    except Exception as e:
        print(f"   ❌ Collection '{COLLECTION_NAME}' tidak ditemukan!")
        print(f"   💡 Coba collection lain: {[c.name for c in collections]}")
    
    # 4. Cek file source JSON
    print(f"\n4. 📄 Cek rag_dataset.json:")
    json_path = Path("rag_dataset.json")
    if json_path.exists():
        import json
        try:
            with open(json_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            print(f"   ✅ File terbaca, berisi {len(data)} entri")
            if len(data) > 0:
                print(f"   📋 Sample entri pertama:")
                sample = data[0]
                print(f"      - id: {sample.get('id')}")
                print(f"      - source: {sample.get('source')}")
                print(f"      - content length: {len(sample.get('content', ''))} chars")
        except Exception as e:
            print(f"   ❌ Gagal parse JSON: {e}")
    else:
        print(f"   ❌ File rag_dataset.json tidak ditemukan di {json_path.absolute()}")
    
    print("\n" + "=" * 60)
    print("💡 Tips:")
    print("   1. Pastikan collection name sama di ingest_chroma.py dan main.py")
    print("   2. Pastikan path chroma_db sama (relative vs absolute path)")
    print("   3. Jalankan ingest_chroma.py dan perhatikan output-nya")
    print("   4. Kalau ragu, hapus folder chroma_db/ lalu ingest ulang dari nol")

if __name__ == "__main__":
    diagnose()