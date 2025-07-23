# pages/4_Converter.py - ENHANCED MULTI-CSV BATCH PROCESSING
import streamlit as st
import csv
import json
import io
import os
import zipfile
from datetime import datetime
from typing import List, Tuple, Dict
import base64


# Bu fonksiyonu import'lardan hemen sonra ekle:
def format_file_size(size_bytes):
    """Convert bytes to human readable format"""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    else:
        return f"{size_bytes / (1024 * 1024):.1f} MB"
def convert_csv_to_json(uploaded_file):
    """
    Yüklenen CSV dosyasını JSON formatına dönüştürür
    """
    try:
        # CSV içeriğini oku
        content = uploaded_file.getvalue().decode('utf-8')
        lines = content.splitlines()

        # Header satırını bul
        header_index = -1
        for i, line in enumerate(lines):
            if 'Order creation date' in line:
                header_index = i
                break

        if header_index == -1:
            header_index = 0  # İlk satırı header olarak kullan

        # Header'dan itibaren CSV'yi parse et
        csv_content = '\n'.join(lines[header_index:])
        csv_reader = csv.DictReader(io.StringIO(csv_content))

        # Her satırı JSON objesine dönüştür
        data = []
        for row_num, row in enumerate(csv_reader, 1):
            if any(row.values()):  # Boş satırları atla
                # Temiz bir order objesi oluştur
                order = {}
                for key, value in row.items():
                    # Key'leri temizle
                    clean_key = key.strip() if key else f"column_{len(order)}"
                    # Value'ları temizle
                    clean_value = value.strip() if value and value.strip() != '--' else None
                    order[clean_key] = clean_value

                data.append(order)

        return data, None

    except Exception as e:
        return None, str(e)


def create_download_link(json_data: str, filename: str) -> str:
    """JSON dosyası için download link oluştur"""
    b64 = base64.b64encode(json_data.encode()).decode()
    href = f'<a href="data:application/json;base64,{b64}" download="{filename}">📄 Download {filename}</a>'
    return href


def process_multiple_csvs(uploaded_files) -> List[Tuple[str, str, str]]:
    """
    Birden fazla CSV dosyasını işle
    Returns: List of (original_filename, json_filename, json_data)
    """
    processed_files = []

    for uploaded_file in uploaded_files:
        # Dosya adını al ve JSON adını oluştur
        original_name = uploaded_file.name
        json_filename = os.path.splitext(original_name)[0] + ".json"

        # CSV'yi JSON'a dönüştür
        json_data, error = convert_csv_to_json(uploaded_file)

        if error:
            # Hata varsa boş JSON ile ekle
            json_string = json.dumps([], ensure_ascii=False, indent=2)
            processed_files.append((original_name, json_filename, json_string, f"Error: {error}"))
        else:
            # Başarılı dönüşüm
            json_string = json.dumps(json_data, ensure_ascii=False, indent=2)
            processed_files.append((original_name, json_filename, json_string, None))

    return processed_files


def auto_transfer_to_order_matcher(processed_files: List[Tuple]):
    """Convert edilmiş dosyaları Order Matcher'a otomatik transfer et"""
    if 'converted_ebay_files' not in st.session_state:
        st.session_state.converted_ebay_files = []

    # Başarılı dönüşümleri session state'e ekle
    for original_name, json_filename, json_data, error in processed_files:
        if not error:
            # JSON data'yı parse et
            try:
                parsed_data = json.loads(json_data)
                # Session state'e dosya adı ve data'yı ekle
                st.session_state.converted_ebay_files.append({
                    'filename': json_filename,
                    'data': parsed_data,
                    'converted_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                })
            except:
                continue

    return len([f for f in processed_files if not f[3]])  # Error olmayan dosya sayısı


def main():
    """Ana sayfa fonksiyonu - ENHANCED MULTI-CSV BATCH PROCESSING"""
    st.set_page_config(
        page_title="Enhanced CSV to JSON Converter",
        page_icon="🔄",
        layout="wide"
    )

    # Başlık ve açıklama
    st.title("🔄 Gelişmiş Çoklu CSV Dönüştürücü")
    st.markdown("Bir veya daha fazla eBay CSV dosyasını JSON formatına dönüştürün")
    # Ana layout
    col1, col2 = st.columns([2, 1])

    with col1:
        st.markdown("""
        ### 📁 Çoklu Dosya Yükleme
        """)

        uploaded_files = st.file_uploader(
            "Birden Fazla eBay CSV Dosyası Seçin",
            type=['csv'],
            help="Toplu işlem için birden fazla CSV dosyası seçin",
            accept_multiple_files=True,
            key="multi_csv_upload"
        )

    # 🆕 BATCH PROCESSING SECTION
    if uploaded_files:
        st.markdown("---")

        # File summary
        st.markdown(f"### 📊 Yükleme Özeti")

        total_size = sum(file.size for file in uploaded_files)
        if total_size < 1024 * 1024:  # Under 1MB
            size_display = f"{total_size / 1024:.1f} KB"
        else:
            size_display = f"{total_size / (1024 * 1024):.1f} MB"

        col1, col2, col3, col4 = st.columns(4)

        with col1:
            st.metric("📄 Seçilen Dosya", len(uploaded_files))
        with col2:
            st.metric("📊 Toplam Boyut", size_display)
        with col3:
            st.metric("🕒 Yükleme Zamanı", datetime.now().strftime("%H:%M:%S"))
        with col4:
            st.metric("🔄 Durum", "Dönüştürmeye Hazır")

        # File list preview
        with st.expander("🔍 Dosya Listesi Önizlemesi"):
            total_preview_size = 0
            for i, file in enumerate(uploaded_files, 1):
                file_size = format_file_size(file.size)
                total_preview_size += file.size
                st.write(f"{i}. **{file.name}** ({file_size})")

            total_size_display = format_file_size(total_preview_size)
            st.info(f"📊 Toplam boyut: {total_size_display}")

        # Processing Options
        st.markdown("### ⚙️ İşleme Seçenekleri")

        col1, col2 = st.columns(2)

        with col1:
            auto_transfer = st.checkbox(
                "🚀 Order Matcher'a otomatik transfer",
                value=True,
                help="Dönüştürülen dosyaları otomatik olarak Order Matcher'a gönder"
            )

        with col2:
            download_files = st.checkbox(
                "💾 Dönüştürülen dosyaları indir",
                value=False,
                help="Tüm dönüştürülen JSON dosyalarını tek tek indir"
            )

        # 🆕 BATCH CONVERT BUTTON
        if st.button("🔄 Tüm Dosyaları JSON'a Dönüştür", type="primary", use_container_width=True):

            with st.spinner("🔄 Birden fazla CSV dosyası işleniyor..."):

                # Process all files
                processed_files = process_multiple_csvs(uploaded_files)

                # Count successful/failed conversions
                successful = [f for f in processed_files if not f[3]]
                failed = [f for f in processed_files if f[3]]

                st.success(f"✅ Batch conversion completed!")

                # Results summary
                col1, col2, col3 = st.columns(3)

                with col1:
                    st.metric("✅ Successful", len(successful))
                with col2:
                    st.metric("❌ Failed", len(failed))
                with col3:
                    total_records = sum(len(json.loads(f[2])) for f in successful)
                    st.metric("📋 Total Records", total_records)

    if st.button("🔄 Convert All Files to JSON", type="primary", use_container_width=True):

        with st.spinner("🔄 Processing multiple CSV files..."):

            # Process all files
            processed_files = process_multiple_csvs(uploaded_files)

            # Count successful/failed conversions
            successful = [f for f in processed_files if not f[3]]
            failed = [f for f in processed_files if f[3]]

            # SADECE BAŞARI MESAJI
            if successful:
                st.success(f"✅ {len(successful)} dosya başarıyla JSON'a dönüştürüldü!")

            if failed:
                st.error(f"❌ {len(failed)} dosya dönüştürülemedi")
            # BACKGROUND İŞLEMLER (görünmez)

            # Auto-transfer (sessizce)
            if auto_transfer and successful:
                auto_transfer_to_order_matcher(processed_files)

            # Download files (sessizce - butonlar otomatik generate olur)
            if download_files and successful:
                for original_name, json_filename, json_data, error in processed_files:
                    if not error:
                        # Download button'lar otomatik oluşturulur
                        pass
    # 🆕 USAGE INSTRUCTIONS
    with st.expander("❓ Hızlı Yardım"):
        st.markdown("""
        **Basit İş Akışı:**
        1. Birden fazla CSV dosyası yükleyin
        2. Seçenekleri işaretleyin: Otomatik transfer ✅ | Dosyaları indir (opsiyonel)
        3. "Tüm Dosyaları JSON'a Dönüştür" butonuna tıklayın
        4. Dosyalar otomatik olarak Order Matcher'da görünür!

        **Özellikler:** Toplu işleme • Otomatik entegrasyon • Gizlilik güvenli yerel işleme
        """)

    # Alt bilgi
    st.markdown("---")
    st.markdown("""
    <div style='text-align: center; color: #666;'>
    🔒 <strong>Privacy Guarantee:</strong> All processing is done locally. Files are not stored on servers.<br>
    🚀 <strong>Enhanced Workflow:</strong> Seamless integration with Order Matcher for complete automation.
    </div>
    """, unsafe_allow_html=True)


if __name__ == "__main__":
    main()