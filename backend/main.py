import os
import asyncio
import logging
import sqlite3
import warnings
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from dotenv import load_dotenv
import google.generativeai as genai
from pathlib import Path

load_dotenv()
warnings.filterwarnings("ignore", category=FutureWarning, module="google.*")

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)-8s | %(message)s")
logger = logging.getLogger(__name__)

SCRIPT_DIR = Path(__file__).parent.resolve()
PROJECT_ROOT = SCRIPT_DIR.parent

DB_PATH = os.getenv("DB_PATH", str(SCRIPT_DIR / "jihs_rag.db"))
COLLECTION_NAME = os.getenv("COLLECTION_NAME", "jihs_rag.db")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.0-flash-001")

if not GEMINI_API_KEY:
    raise ValueError("❌ GEMINI_API_KEY tidak ditemukan!")

genai.configure(api_key=GEMINI_API_KEY)
gemini_model = genai.GenerativeModel(GEMINI_MODEL)
logger.info(f"✅ Gemini loaded: {GEMINI_MODEL}")

app = FastAPI(title="JIHS RAG Backend (SQLite)", version="1.0.0")

from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Untuk development
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

logger.info(f"🗄️  Backend DB Path: {DB_PATH}")
logger.info(f"🗄️  File exists: {Path(DB_PATH).exists()}")

class ChatRequest(BaseModel):
    message: str = Field(..., min_length=2, max_length=1000)

class ChatResponse(BaseModel):
    answer: str
    sources: list[str]

def retrieve_chunks(query: str, n_results: int = 5) -> list[dict]:
    """Keyword search dengan ekstraksi keyword penting"""
    import re
    
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    
    logger.info(f"🔍 Query asli: '{query}'")
    
    # Ekstrak keyword penting (huruf kapital atau kata kunci spesifik)
    # Hapus stop words Indonesia
    stop_words = {
        'yang', 'di', 'dan', 'atau', 'untuk', 'dari', 'pada', 'dalam',
        'apakah', 'ada', 'apa', 'saya', 'mau', 'ingin', 'bisa', 'tolong',
        'tentang', 'cara', 'how', 'what', 'is', 'are', 'do', 'does',
        'apakah', 'dimana', 'kemana', 'berapa', 'siapa', 'kapan',
        'ini', 'itu', 'itu', 'dengan', 'tanpa', 'ke', 'dari'
    }
    
    # Tokenize & filter
    words = re.findall(r'\b\w+\b', query.lower())
    keywords = [w for w in words if len(w) > 3 and w not in stop_words]
    
    logger.info(f"🔑 Keywords diekstrak: {keywords}")
    
    # Cari dengan keyword terbaik (prioritas yang paling spesifik)
    # Coba cari "pastry" dulu
    results = []
    for keyword in keywords:
        term = f"%{keyword}%"
        logger.info(f"🔎 Mencari keyword: '{keyword}'")
        
        partial_results = conn.execute("""
            SELECT * FROM chunks
            WHERE LOWER(content) LIKE ? 
               OR LOWER(section_heading) LIKE ?
            LIMIT ?
        """, (term, term, 3)).fetchall()
        
        if partial_results:
            logger.info(f"   ✅ Ditemukan {len(partial_results)} dokumen")
            results.extend(partial_results)
        else:
            logger.info(f"   ❌ Tidak ditemukan")
    
    # Remove duplicates & limit
    seen_ids = set()
    unique_results = []
    for r in results:
        if r['id'] not in seen_ids:
            seen_ids.add(r['id'])
            unique_results.append(r)
    
    final_results = unique_results[:n_results]
    
    logger.info(f"📊 Total hasil unik: {len(final_results)} dokumen")
    
    conn.close()
    return [dict(row) for row in final_results]

async def generate_with_gemini(prompt: str, temperature: float = 0.1) -> str:
    loop = asyncio.get_event_loop()
    def _generate():
        try:
            response = gemini_model.generate_content(
                prompt,
                generation_config=genai.types.GenerationConfig(
                    temperature=temperature,
                    max_output_tokens=1024,
                )
            )
            return response.text.strip()
        except Exception as e:
            logger.error(f"❌ Gemini error: {e}")
            return "Maaf, terjadi kesalahan saat memproses jawaban. Silakan coba lagi."
    return await loop.run_in_executor(None, _generate)

@app.post("/api/chat", response_model=ChatResponse)
async def chat_endpoint(request: ChatRequest):
    try:
        chunks = retrieve_chunks(request.message, n_results=5)
        
        if not chunks:
            fallback = f"""
            Kamu adalah asisten AI resmi Politeknik Jakarta Internasional (JIHS).
            User bertanya: "{request.message}"
            Informasi ini belum tersedia di database internal. 
            Arahkan user ke Admisi JIHS atau jihs.ac.id dengan bahasa sopan.
            """
            return ChatResponse(answer=await generate_with_gemini(fallback), sources=[])
        
        context = "\n\n---\n\n".join([c["content"] for c in chunks])
        sources = list(set(c["source"] for c in chunks if c.get("source")))
        
        prompt = f"""
        Kamu adalah asisten AI resmi JIHS. Jawab HANYA berdasarkan konteks berikut:

        [KONTEKS]
        {context}

        [ATURAN]
        1. Akurat, langsung, relevan.
        2. Jika ada placeholder ([INPUT_...]), sebutkan ini estimasi.
        3. Jika konteks tidak cukup, akui & arahkan ke Admisi.
        4. Bahasa Indonesia profesional & terstruktur.

        [PERTANYAAN]
        {request.message}
        """
        
        return ChatResponse(answer=await generate_with_gemini(prompt), sources=sources)
    except Exception as e:
        logger.error(f"💥 Error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")

@app.get("/health")
async def health_check():
    conn = sqlite3.connect(DB_PATH)
    count = conn.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]
    conn.close()
    return {"status": "healthy", "database": "SQLite", "total_chunks": count, "model": GEMINI_MODEL}

@app.get("/")
async def root():
    return {"message": "🎓 JIHS RAG Backend (SQLite) ready!", "docs": "/docs", "health": "/health"}

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8001))
    logger.info(f"🚀 Starting on http://0.0.0.0:{port}")
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")