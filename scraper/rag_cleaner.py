import json
import os
import re
import hashlib
from datetime import datetime

# ⚙️ KONFIGURASI RAG
CONFIG = {
    "chunk_size": 800,           # Target karakter per chunk (±300-500 tokens)
    "chunk_overlap": 100,        # Overlap antar chunk agar konteks tidak putus
    "min_chunk_size": 150,       # Buang chunk terlalu pendek (noise)
    "preserve_headings": True,   # Simpan heading sebagai metadata terpisah
    "extract_keywords": True,    # Ekstrak kata kunci sederhana untuk hybrid search
    "output_format": "jsonl",    # "jsonl" (recommended for RAG) atau "json"
}

def generate_chunk_id(source: str, chunk_index: int, content: str) -> str:
    """Generate unique ID untuk setiap chunk"""
    hash_input = f"{source}:{chunk_index}:{content[:100]}"
    return hashlib.md5(hash_input.encode()).hexdigest()[:12]

def extract_headings_and_sections(text: str) -> list:
    """
    Pecah teks menjadi sections berdasarkan heading.
    Heading: baris pendek (<70 char) + all caps / berakhir dengan ':'
    Returns: list of dict {heading: str, content: str, start_pos: int}
    """
    lines = text.split('\n')
    sections = []
    current_heading = "Pendahuluan"
    current_content = []
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
        
        # Deteksi heading
        is_heading = (
            len(line) < 70 and 
            (line.isupper() or line.endswith(':') or line.endswith('—')) and
            not line.endswith('.') and  # Bukan kalimat lengkap
            not any(c in line for c in '0123456789')  # Bukan nomor list
        )
        
        if is_heading:
            # Simpan section sebelumnya
            if current_content:
                sections.append({
                    "heading": current_heading,
                    "content": "\n".join(current_content).strip(),
                    "word_count": len(" ".join(current_content).split())
                })
            # Mulai section baru
            current_heading = line.rstrip(':').strip()
            current_content = []
        else:
            current_content.append(line)
    
    # Simpan section terakhir
    if current_content:
        sections.append({
            "heading": current_heading,
            "content": "\n".join(current_content).strip(),
            "word_count": len(" ".join(current_content).split())
        })
    
    return sections

def smart_chunk_text(text: str, chunk_size: int, overlap: int, heading: str = "") -> list:
    """
    Chunking cerdas: potong di batas kalimat/paragraf, bukan di tengah kata.
    Returns: list of chunk strings
    """
    if len(text) <= chunk_size:
        return [text] if len(text) > CONFIG["min_chunk_size"] else []
    
    chunks = []
    start = 0
    
    while start < len(text):
        end = start + chunk_size
        
        # Jika sudah di akhir, ambil sisa
        if end >= len(text):
            chunk = text[start:].strip()
            if len(chunk) >= CONFIG["min_chunk_size"]:
                chunks.append(chunk)
            break
        
        # Cari batas potong optimal:
        # 1. Prioritas: double newline (paragraf)
        # 2. Secondary: titik + spasi (akhir kalimat)
        # 3. Fallback: spasi (akhir kata)
        
        window = text[start:end+50]  # Buffer untuk cari batas
        
        # Coba cari paragraf break
        para_break = window.rfind('\n\n')
        if para_break > chunk_size * 0.7:  # Minimal di 70% chunk
            end = start + para_break
        else:
            # Coba cari akhir kalimat
            sentence_end = re.search(r'[.!?]\s', window[-chunk_size//2:])
            if sentence_end:
                end = start + chunk_size//2 + sentence_end.end()
            else:
                # Fallback: cari spasi terakhir
                last_space = window.rfind(' ')
                if last_space > chunk_size * 0.5:
                    end = start + last_space
        
        chunk = text[start:end].strip()
        
        # Hanya simpan jika cukup panjang
        if len(chunk) >= CONFIG["min_chunk_size"]:
            # Tambahkan heading sebagai prefix jika diaktifkan
            if CONFIG["preserve_headings"] and heading and not chunk.startswith(heading):
                chunk = f"{heading}: {chunk}"
            chunks.append(chunk)
        
        # Geser start dengan overlap
        start = end - overlap
        
        # Safety: hindari infinite loop
        if start >= len(text) - CONFIG["min_chunk_size"]:
            break
    
    return chunks

def extract_simple_keywords(text: str, top_k: int = 10) -> list:
    """Ekstrak kata kunci sederhana (frekuensi + panjang kata)"""
    # Hapus punctuation, lowercase
    words = re.findall(r'\b[a-z\-\+]{4,}\b', text.lower())
    
    # Stopwords sederhana (bisa diperluas)
    stopwords = {
        'dengan', 'untuk', 'yang', 'dan', 'atau', 'dari', 'pada', 'dalam',
        'adalah', 'merupakan', 'sebagai', 'oleh', 'ke', 'di', 'kepada',
        'the', 'and', 'for', 'with', 'from', 'this', 'that', 'have', 'has'
    }
    
    # Hitung frekuensi
    from collections import Counter
    filtered = [w for w in words if w not in stopwords]
    freq = Counter(filtered)
    
    # Ambil top-k + bobot panjang kata
    scored = {w: c * (len(w) / 5) for w, c in freq.most_common(top_k * 2)}
    return sorted(scored.keys(), key=lambda x: scored[x], reverse=True)[:top_k]

def clean_for_rag(text: str) -> str:
    """Cleaning khusus untuk RAG: maksimal preservasi makna, minimal noise"""
    
    # 1. Normalisasi whitespace
    text = re.sub(r'[ \t]+', ' ', text)
    text = re.sub(r'\s+\n', '\n', text)
    
    # 2. Fix punctuation spacing
    text = re.sub(r'\s+([.,;:!?])', r'\1', text)
    text = re.sub(r'\(\s+', r'(', text)
    text = re.sub(r'\s+\)', r')', text)
    text = re.sub(r'\s+%', r'%', text)
    
    # 3. Hapus noise patterns spesifik
    noise_patterns = [
        r'^Contact Us\s*$',
        r'^Registrasi Sekarang\s*$',
        r'^How can we help\s*\??\s*$',
        r'^SCBD Lot\.\d+.*$',
        r'^\+62\s*[\d\-\s]+.*$',
        r'^Fax\s*\+62.*$',
        r'^info@[\w\.-]+\.[\w]+$',
        r'^@\d{4}\s*\w*$',
        r'^Privacy Policy\s*\|.*$',
        r'^Scroll to top\s*$',
        r'^Kembali ke atas\s*$',
    ]
    for pattern in noise_patterns:
        text = re.sub(pattern, '', text, flags=re.MULTILINE | re.IGNORECASE)
    
    # 4. Hapus baris terlalu pendek yang bukan heading
    lines = text.split('\n')
    cleaned_lines = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        if len(line) < 25:
            # Pertahankan jika heading atau kalimat lengkap
            if not (line.isupper() or any(p in line for p in '.!?:')):
                continue
        cleaned_lines.append(line)
    
    return '\n'.join(cleaned_lines).strip()

def process_file(filepath: str) -> list:
    """Proses satu file .txt menjadi list of RAG chunks"""
    with open(filepath, "r", encoding="utf-8") as f:
        lines = f.readlines()
    
    if not lines:
        return []
    
    # Parse metadata
    source = lines[0].replace("SOURCE: ", "").strip() if lines else "Unknown"
    scraped_at = lines[1].replace("SCRAPED_AT: ", "").strip() if len(lines) > 1 else None
    
    # Ambil konten (skip 3 baris header: SOURCE, SCRAPED_AT, ===)
    raw_content = "".join(lines[3:]).strip()
    
    # Cleaning dasar
    clean_content = clean_for_rag(raw_content)
    if len(clean_content) < CONFIG["min_chunk_size"]:
        return []  # Skip konten terlalu pendek
    
    # Ekstrak sections berdasarkan heading
    sections = extract_headings_and_sections(clean_content)
    
    # Generate chunks per section
    chunks = []
    chunk_index = 0
    
    for section in sections:
        heading = section["heading"]
        content = section["content"]
        
        # Chunking
        section_chunks = smart_chunk_text(
            content, 
            CONFIG["chunk_size"], 
            CONFIG["chunk_overlap"],
            heading if CONFIG["preserve_headings"] else ""
        )
        
        for chunk_text in section_chunks:
            # Ekstrak keywords jika diaktifkan
            keywords = extract_simple_keywords(chunk_text) if CONFIG["extract_keywords"] else []
            
            chunk = {
                "id": generate_chunk_id(source, chunk_index, chunk_text),
                "source": source,
                "source_filename": os.path.basename(filepath).replace(".txt", ""),
                "section_heading": heading if CONFIG["preserve_headings"] else None,
                "content": chunk_text,
                "metadata": {
                    "char_count": len(chunk_text),
                    "word_count": len(chunk_text.split()),
                    "chunk_index": chunk_index,
                    "total_chunks_in_doc": None,  # Akan di-set nanti
                    "keywords": keywords,
                    "language": "id",  # Asumsi bahasa Indonesia
                    "scraped_at": scraped_at,
                    "processed_at": datetime.now().isoformat()
                }
            }
            chunks.append(chunk)
            chunk_index += 1
    
    # Update total_chunks_in_doc
    total = len(chunks)
    for i, chunk in enumerate(chunks):
        chunk["metadata"]["total_chunks_in_doc"] = total
    
    return chunks

def convert_to_rag_format():
    """Main function: konversi semua file di data_raw ke format RAG"""
    raw_dir = "data_raw"
    clean_dir = "data_clean"
    
    if not os.path.exists(clean_dir):
        os.makedirs(clean_dir)
    
    all_chunks = []
    stats = {"files_processed": 0, "total_chunks": 0, "skipped": 0}
    
    print(f"🔄 Memproses file dari {raw_dir}/ ...")
    
    for filename in sorted(os.listdir(raw_dir)):
        if not filename.endswith(".txt"):
            continue
        
        filepath = os.path.join(raw_dir, filename)
        print(f"  📄 {filename}...", end=" ")
        
        try:
            chunks = process_file(filepath)
            
            if not chunks:
                print("⚠ (dilewati: konten terlalu pendek)")
                stats["skipped"] += 1
                continue
            
            all_chunks.extend(chunks)
            stats["files_processed"] += 1
            stats["total_chunks"] += len(chunks)
            print(f"✓ {len(chunks)} chunks")
            
        except Exception as e:
            print(f"✘ Error: {e}")
            continue
    
    if not all_chunks:
        print("\n❌ Tidak ada chunk yang berhasil diproses.")
        return
    
    # 📦 Export: JSONL (recommended untuk RAG pipelines)
    if CONFIG["output_format"] == "jsonl":
        jsonl_path = os.path.join(clean_dir, "rag_dataset.jsonl")
        with open(jsonl_path, "w", encoding="utf-8") as f:
            for chunk in all_chunks:
                f.write(json.dumps(chunk, ensure_ascii=False) + "\n")
        print(f"\n✓ Exported: {jsonl_path} ({len(all_chunks)} chunks)")
    
    # 📦 Export: Master JSON (untuk backup/inspeksi)
    json_path = os.path.join(clean_dir, "rag_dataset.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(all_chunks, f, indent=2, ensure_ascii=False)
    print(f"✓ Exported: {json_path}")
    
    # 📊 Print stats
    print(f"\n📊 Statistik:")
    print(f"   • File diproses: {stats['files_processed']}")
    print(f"   • Total chunks: {stats['total_chunks']}")
    print(f"   • Dilewati: {stats['skipped']}")
    print(f"   • Rata-rata chunk: {sum(c['metadata']['word_count'] for c in all_chunks)/len(all_chunks):.0f} kata")
    
    # 🎯 Preview 1 chunk contoh
    print(f"\n🔍 Preview chunk pertama:")
    print("-" * 60)
    preview = all_chunks[0]
    print(f"ID: {preview['id']}")
    print(f"Source: {preview['source']}")
    print(f"Section: {preview['section_heading']}")
    print(f"Content: {preview['content'][:200]}...")
    print(f"Keywords: {preview['metadata']['keywords'][:5]}")
    print("-" * 60)

if __name__ == "__main__":
    convert_to_rag_format()