import os
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

if not GEMINI_API_KEY:
    print("❌ GEMINI_API_KEY tidak ditemukan di .env!")
    exit(1)

print(f"🔑 Menggunakan API Key: {GEMINI_API_KEY[:15]}...")
genai.configure(api_key=GEMINI_API_KEY)

print("\n🔍 Model yang mendukung generateContent:")
print("=" * 70)
found = False
for model in genai.list_models():
    if 'generateContent' in model.supported_generation_methods:
        print(f"✅ {model.name}")
        found = True
        # Ambil nama pertama sebagai rekomendasi
        if not os.getenv("GEMINI_MODEL"):
            recommended = model.name.replace("models/", "")
            print(f"\n💡 Rekomendasi: Set GEMINI_MODEL={recommended} di .env")

if not found:
    print("❌ Tidak ada model yang tersedia. Cek API Key atau quota!")
print("=" * 70)