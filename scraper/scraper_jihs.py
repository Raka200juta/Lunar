from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup
import os
import time
import random
import re
from urllib.parse import urlparse

# DAFTAR LINK HASIL HARVESTING
urls_to_scrape = [
    'https://jihs.ac.id/',
    'https://jihs.ac.id/sambutan',
    'https://jihs.ac.id/tentang-kami',
    'https://jihs.ac.id/sejarah',
    'https://jihs.ac.id/visi-misi',
    'https://jihs.ac.id/akreditasi',
    'https://jihs.ac.id/prestasi',
    'https://jihs.ac.id/jajaran-manajemen',
    'https://jihs.ac.id/dosen',
    'https://jihs.ac.id/mitra-kami',
    'https://jihs.ac.id/akademik?id=0',
    'https://jihs.ac.id/akademik?id=1',
    'https://jihs.ac.id/akademik?id=2',
    'https://jihs.ac.id/akademik?id=3',
    'https://jihs.ac.id/akademik?id=4',
    'https://jihs.ac.id/akademik?id=6',
    'https://jihs.ac.id/akademik?id=7',
    'https://jihs.ac.id/akademik?id=8',
    'https://jihs.ac.id/berita-kampus',
    'https://jihs.ac.id/kisah-sukses',
    'https://jihs.ac.id/kata-mahasiswa',
    'https://jihs.ac.id/fasilitas-kampus',
    'https://jihs.ac.id/gallery',
    'https://jihs.ac.id/video',
    'https://jihs.ac.id/info-pendaftaran/1',
    'https://jihs.ac.id/info-pendaftaran/2',
    'https://jihs.ac.id/info-pendaftaran/4'
]

def clean_filename(url):
    parsed = urlparse(url)
    path = parsed.path.strip("/").replace("/", "_")
    query = parsed.query.replace("=", "_")
    filename = f"{path}_{query}" if query else path
    return filename or "home"

def setup_driver():
    """Setup Chrome driver dengan mode headless + stealth"""
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option("useAutomationExtension", False)
    
    driver = webdriver.Chrome(
        service=Service(ChromeDriverManager().install()),
        options=chrome_options
    )
    driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
        "source": """
            Object.defineProperty(navigator, 'webdriver', {get: () => undefined})
        """
    })
    return driver

def remove_noise_elements(soup):
    """Hapus elemen-elemen noise dari BeautifulSoup object"""
    
    # 1. Hapus tag yang jelas-jelas noise
    noise_tags = [
        'script', 'style', 'nav', 'footer', 'header', 'iframe', 'noscript',
        'form', 'button', 'input', 'select', 'textarea', 'svg', 'canvas',
        'aside', 'menu', 'dialog', 'details', 'summary', 'figure', 'figcaption'
    ]
    for tag in noise_tags:
        for element in soup.find_all(tag):
            element.decompose()
    
    # 2. Hapus elemen berdasarkan class/id umum (WordPress/Bootstrap patterns)
    noise_patterns = [
        # Class patterns
        r'.*sidebar.*', r'.*widget.*', r'.*social.*', r'.*share.*', r'.*comment.*',
        r'.*cookie.*', r'.*banner.*', r'.*popup.*', r'.*modal.*', r'.*ads.*',
        r'.*advertisement.*', r'.*newsletter.*', r'.*subscribe.*', r'.*contact.*form.*',
        r'.*whatsapp.*', r'.*chat.*', r'.*scroll.*top.*', r'.*back.*to.*top.*',
        r'.*menu.*', r'.*navigation.*', r'.*breadcrumb.*', r'.*pagination.*',
        
        # ID patterns
        r'^sidebar', r'^widget', r'^social', r'^cookie', r'^banner',
        r'^popup', r'^modal', r'^ads', r'^newsletter'
    ]
    
    for element in soup.find_all(True):  # Semua tag
        if element.get('class'):
            classes = ' '.join(element['class']).lower()
            if any(re.match(pat, classes, re.IGNORECASE) for pat in noise_patterns):
                element.decompose()
                continue
        if element.get('id'):
            elem_id = element['id'].lower()
            if any(re.match(pat, elem_id, re.IGNORECASE) for pat in noise_patterns):
                element.decompose()
    
    # 3. Hapus elemen dengan atribut tertentu
    for element in soup.find_all(attrs={'aria-hidden': 'true'}):
        element.decompose()
    for element in soup.find_all(attrs={'hidden': True}):
        element.decompose()
    
    # 4. Hapus link-only elements yang biasanya noise
    for link in soup.find_all('a', href=True):
        link_text = link.get_text(strip=True).lower()
        if any(kw in link_text for kw in [
            'privacy policy', 'terms', 'cookie', 'subscribe', 'follow us',
            'whatsapp', 'chat', 'klik disini', 'daftar sekarang', 'registrasi'
        ]):
            # Hapus hanya jika link ini berdiri sendiri atau di container kecil
            parent = link.parent
            if parent and len(parent.get_text(strip=True)) < 100:
                parent.decompose()
    
    return soup

def extract_main_content(soup):
    """Ekstrak konten utama dengan prioritas selector"""
    
    # Prioritas selector dari yang paling spesifik ke umum
    selectors = [
        # WordPress themes
        'main#main', 'article.post', 'div.entry-content', 'div.post-content',
        # Generic content containers
        'main', 'article', 'section.content', 'div.content', 'div#content',
        # Page-specific
        'div.page-content', 'div.article-body', 'div.text-content',
        # Fallback ke body tapi hapus children yang masih noise
        'body'
    ]
    
    for selector in selectors:
        # Handle CSS selector vs simple tag
        if '#' in selector or '.' in selector:
            element = soup.select_one(selector)
        else:
            element = soup.find(selector)
        
        if element and len(element.get_text(strip=True)) > 100:  # Minimal 100 char
            return element
    
    # Fallback terakhir: body
    return soup.body

def clean_extracted_text(text: str) -> str:
    """Bersihkan teks hasil extract: rejoin kalimat, hapus noise, fix formatting"""
    
    # 1. Normalisasi whitespace
    text = re.sub(r'[ \t]+', ' ', text)
    text = re.sub(r'\s+\n', '\n', text)
    
    # 2. Rejoin kalimat yang terpotong line break
    lines = [l.strip() for l in text.split('\n') if l.strip()]
    rejoined = []
    buffer = ""
    
    for line in lines:
        if not buffer:
            buffer = line
            continue
        
        last_char = buffer[-1] if buffer else ""
        first_char = line[0] if line else ""
        
        # Lanjutkan kalimat jika: tidak berakhir dengan [.!?:] DAN mulai dengan lowercase/angka
        is_continuation = (
            last_char not in '.!?:' and
            (first_char.islower() or first_char.isdigit() or first_char in '"\'(') and
            not (len(line) < 50 and line.isupper())  # Bukan heading
        )
        
        if is_continuation and len(buffer) < 200:  # Jangan join kalau sudah panjang
            buffer += " " + line
        else:
            rejoined.append(buffer)
            buffer = line
    
    if buffer:
        rejoined.append(buffer)
    
    # 3. Hapus noise keywords spesifik jihs.ac.id
    noise_keywords = [
        'Contact Us', 'Registrasi Sekarang', 'How can we help?',
        'SCBD Lot.21', 'Jl. Jend. Sudirman', 'Kebayoran Baru', 'Jakarta Selatan',
        '+62 21', 'Fax +62', 'info@jihs.ac.id', '@2023', '@2024', 'IAT',
        'Privacy Policy', 'Terms of Service', 'Kembali ke atas', 'Scroll to top',
        'WhatsApp', 'Chat dengan kami', 'Follow us', 'Subscribe',
        'Download', 'Share this', 'Lihat juga', 'Baca juga',
        'Kata Mahasiswa', 'Kisah Sukses', 'Gallery', 'Video',
        'Akademik', 'Program Studi', 'Daftar Sekarang', 'Pendaftaran'
    ]
    
    filtered = []
    skip_mode = False
    
    for line in rejoined:
        # Deteksi section footer (biasanya setelah "Contact Us" atau "Registrasi")
        if any(kw.lower() in line.lower() for kw in ['contact us', 'registrasi sekarang', 'how can we help', 'footer']):
            skip_mode = True
            continue
        if skip_mode:
            continue
        
        # Skip baris dengan noise keywords
        if any(kw.lower() in line.lower() for kw in noise_keywords):
            continue
        
        # Skip baris terlalu pendek yang bukan heading/punctuation
        if len(line) < 20:
            if not (line.isupper() and len(line) < 60):  # Kecuali heading kapital
                if not any(p in line for p in '.!?:'):  # Atau kalimat lengkap pendek
                    continue
        
        # Skip baris yang hanya angka/tanggal (biasanya metadata)
        if re.match(r'^[\d\s\-\./:]+$', line) and len(line) < 30:
            continue
            
        filtered.append(line)
    
    # 4. Fix spacing & punctuation
    text = '\n'.join(filtered)
    text = re.sub(r'\s+([.,;:!?])', r'\1', text)      # Hapus spasi sebelum tanda baca
    text = re.sub(r'\(\s+', r'(', text)                # Hapus spasi setelah (
    text = re.sub(r'\s+\)', r')', text)                # Hapus spasi sebelum )
    text = re.sub(r'\s+%', r'%', text)                 # Fix "87 %" → "87%"
    text = re.sub(r'\s+', ' ', text)                   # Normalize internal spaces
    
    # 5. Formatting: blank line untuk heading & paragraf
    paragraphs = []
    for line in text.split('\n'):
        line = line.strip()
        if not line:
            continue
        
        # Heading: pendek + kapital/berakhiran : → tambah blank line sebelumnya
        is_heading = (len(line) < 70 and 
                     (line.isupper() or line.endswith(':') or line.endswith('—')))
        
        if is_heading and paragraphs and paragraphs[-1].strip():
            paragraphs.append('')  # Blank line sebelum heading
        paragraphs.append(line)
    
    # 6. Final cleanup
    result = '\n'.join(paragraphs)
    result = re.sub(r'\n{3,}', '\n\n', result)  # Max 2 newline
    result = re.sub(r' {2,}', ' ', result)       # Max 1 space
    
    return result.strip()

def execute_sniper():
    if not os.path.exists("data_raw"):
        os.makedirs("data_raw")

    driver = setup_driver()
    
    try:
        for idx, url in enumerate(urls_to_scrape, 1):
            name = clean_filename(url)
            path = os.path.join("data_raw", f"{name}.txt")

            if os.path.exists(path):
                print(f"[{idx}/{len(urls_to_scrape)}] - Skip: {name}.txt (Sudah ada)")
                continue

            try:
                wait = random.uniform(7, 15)
                print(f"[{idx}/{len(urls_to_scrape)}] Menunggu {wait:.2f}s... {url}")
                time.sleep(wait)

                driver.get(url)
                
                # Tunggu render + AJAX
                try:
                    WebDriverWait(driver, 20).until(
                        EC.presence_of_element_located((By.TAG_NAME, "body"))
                    )
                    time.sleep(2)  # Tunggu AJAX singkat
                except:
                    pass
                
                html = driver.page_source
                soup = BeautifulSoup(html, 'html.parser')
                
                # 🔥 STEP 1: Hapus noise elements di level HTML
                soup = remove_noise_elements(soup)
                
                # 🔥 STEP 2: Ekstrak hanya konten utama
                main_content = extract_main_content(soup)
                
                if not main_content:
                    print(f"⚠ Warning: Tidak ditemukan konten utama untuk {url}")
                    continue
                
                raw_text = main_content.get_text(separator="\n", strip=True)
                
                # 🔥 STEP 3: Bersihkan teks dengan cleaning function
                clean_text = clean_extracted_text(raw_text)
                
                # Skip jika hasil terlalu pendek (mungkin gagal extract)
                if len(clean_text) < 100:
                    print(f"⚠ Warning: Konten terlalu pendek untuk {url} ({len(clean_text)} chars)")
                    continue
                
                # Simpan dengan metadata
                with open(path, "w", encoding="utf-8") as f:
                    f.write(f"SOURCE: {url}\n")
                    f.write(f"SCRAPED_AT: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
                    f.write("=" * 80 + "\n\n")
                    f.write(clean_text)
                
                stats = f"{len(clean_text)} chars, {clean_text.count(chr(10))+1} lines"
                print(f"✓ Berhasil: {name}.txt [{stats}]")

            except Exception as e:
                print(f"✘ Error pada {url}: {e}")
                continue

    finally:
        driver.quit()
        print("\n✓ Semua selesai. Driver ditutup.")

if __name__ == "__main__":
    execute_sniper()