import streamlit as st
import pandas as pd
import time
import json
from PIL import Image
import io 
from geopy.geocoders import Nominatim
from google import genai 
# Tambahkan import st untuk mengakses st.secrets
import streamlit as st 

# --- KONFIGURASI DAN INISIALISASI ---

# PENTING: Kunci API diambil dari file .streamlit/secrets.toml
# Ini adalah perubahan krusial agar bisa berjalan di Streamlit Cloud!
client = genai.Client(api_key=st.secrets["GEMINI_API_KEY"])
model = 'gemini-2.5-flash' 

# INISIALISASI NOMINATIM
geolocator = Nominatim(user_agent="PUPR Papua Tengah Data Akuntabilitas System Demo")

# PROMPT EKSTRAKSI (TETAP SAMA)
PROMPT_EKSTRAKSI = (
    "Anda adalah sistem ekstraksi data KTP profesional. Dari gambar KTP ini, "
    "ekstrak data berikut: NIK, NAMA, Alamat, dan Kabupaten/Kota. Gabungkan Tempat Lahir dan Tanggal Lahir menjadi 'TTL' dengan format 'Tempat, DD-MM-YYYY'. "
    "Sajikan hasilnya HANYA dalam format JSON dengan keys: NIK, NAMA, TTL, ALAMAT, KABUPATEN/KOTA. Jangan tambahkan penjelasan apapun."
)

# --- FUNGSI UTAMA PEMROSESAN ---
def process_ktp(img):
    """Menggabungkan OCR Gemini dan Geocoding Nominatim."""
    st.info("🤖 Memproses data KTP menggunakan Gemini...")
    
    # 1. OCR GEMINI
    start_time = time.time()
    response = client.models.generate_content(model=model, contents=[PROMPT_EKSTRAKSI, img])
    end_time = time.time()
    extraction_time = round(end_time - start_time, 2)
    
    # Pembersihan JSON 
    json_teks = response.text.strip()
    if json_teks.startswith('```json'):
        json_teks = json_teks[7:]
    if json_teks.endswith('```'):
        json_teks = json_teks[:-3]
    json_teks = json_teks.strip()

    # Handle error jika Gemini tidak mengembalikan JSON yang valid
    try:
        data_ekstrak = json.loads(json_teks)
    except json.JSONDecodeError:
        st.error(f"Gagal memparsing JSON dari Gemini. Output mentah: {json_teks[:100]}...")
        return {
            'NIK': 'Error JSON',
            'NAMA': 'Error JSON',
            'TTL': 'Error JSON',
            'ALAMAT_TEKS': 'Error JSON',
            'KABUPATEN/KOTA': 'Error JSON',
            'KOORDINAT': 'Gagal (JSON Error)',
            'LAT': None,
            'LON': None,
            'WAKTU (dtk)': extraction_time
        }
    
    alamat_gemini = data_ekstrak.get('ALAMAT', '')
    kabupaten_gemini = data_ekstrak.get('KABUPATEN/KOTA', '')
    
    # 2. GEOCODING (KOORDINAT LOW-COST)
    # Gunakan alamat lengkap untuk pencarian koordinat
    alamat_lengkap = alamat_gemini + ", " + kabupaten_gemini + ", Papua Tengah" 
    koordinat = "Gagal Ditemukan (Nominatim)"
    lat, lon = None, None

    try:
        st.info(f"🌍 Mencari koordinat untuk: {alamat_lengkap}")
        # Atur timeout agar tidak terlalu lama
        location = geolocator.geocode(alamat_lengkap, timeout=10) 
        
        if location:
            lat = round(location.latitude, 6) 
            lon = round(location.longitude, 6)
            koordinat = f"{lat}, {lon}"
            
        time.sleep(1.5) # Jeda agar tidak terkena rate limit Nominatim
    except Exception as geo_e:
        koordinat = f"Error Geocoding: {type(geo_e).__name__}"
    
    # 3. KUMPULKAN HASIL
    results = {
        'NIK': data_ekstrak.get('NIK', 'TIDAK DITEMUKAN'),
        'NAMA': data_ekstrak.get('NAMA', ''),
        'TTL': data_ekstrak.get('TTL', ''),
        'ALAMAT_TEKS': alamat_gemini,
        'KABUPATEN/KOTA': kabupaten_gemini,
        'KOORDINAT': koordinat,
        'LAT': lat,
        'LON': lon,
        'WAKTU (dtk)': extraction_time
    }
    
    return results

# --- TATA LETAK STREAMLIT (THE UI) ---

st.set_page_config(
    page_title="PUPR: Sistem Akuntabilitas Data Spasial Berbasis AI",
    layout="wide"
)

st.title("🏡 Sistem Validasi Data KTP Cerdas (Gemini + Geocoding)")
st.caption("Inovasi Low-Cost untuk Akuntabilitas Program Bantuan Rumah")

# 1. INPUT FILE
uploaded_file = st.file_uploader(
    "Unggah Gambar KTP/KK (JPG/PNG)",
    type=['jpg', 'png', 'jpeg'],
    help="Hanya satu file yang dapat diproses sebagai demo."
)

if uploaded_file is not None:
    col1, col2 = st.columns(2)
    with col1:
        img = Image.open(uploaded_file)
        st.image(img, caption='KTP/KK yang Diunggah', use_column_width=True)

    with col2:
        if st.button("🚀 PROSES DATA & CEK KOORDINAT", type="primary"):
            st.warning("Memulai Pemrosesan... Harap tunggu 5-10 detik.")
            
            # Panggil fungsi pemrosesan utama
            results = process_ktp(img)
            
            st.success("✅ PEMROSESAN SELESAI!")
            
            st.subheader("📝 Hasil Ekstraksi Data (Audit Trail)")
            df_results = pd.DataFrame([results])
            st.table(df_results[['NIK', 'NAMA', 'TTL', 'KABUPATEN/KOTA', 'WAKTU (dtk)']])
            
            st.subheader("📍 Validasi Akuntabilitas Spasial")
            
            if results['LAT'] and results['LON']:
                st.success(f"KOORDINAT DITEMUKAN: **{results['KOORDINAT']}**")
                
                # Menampilkan peta
                map_data = pd.DataFrame({
                    'lat': [results['LAT']],
                    'lon': [results['LON']]
                })
                
                st.map(map_data, zoom=12) 
                st.markdown(f"**Alamat Teks dari KTP:** *{results['ALAMAT_TEKS']}*")
            else:
                st.error(f"KOORDINAT GAGAL DITEMUKAN. Pesan: {results['KOORDINAT']}")
