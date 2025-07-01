import streamlit as st
import csv
import json
import io
import os
from datetime import datetime

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

def main():
    """Ana sayfa fonksiyonu"""
    st.set_page_config(
        page_title="CSV to JSON Converter",
        page_icon="🔄",
        layout="wide"
    )

    # Başlık ve açıklama
    st.title("CSV to JSON Converter")
    st.markdown("---")

    col1, col2 = st.columns([2, 1])

    with col1:
        st.markdown("""
        ### 📁 File Upload
        Drag and drop your CSV file below or use the file selector.
        """)

        # Dosya yükleme alanı
        uploaded_file = st.file_uploader(
            "Select CSV File",
            type=['csv'],
            help="Maximum file size: 200MB"
        )

    with col2:
        st.markdown("""
        ### ℹ️ Information
        - ✅ Drag & Drop supported
        - 🔒 Privacy protected
        - 🗑️ Data deleted after processing
        - 💾 Downloaded as JSON
        """)

    # Dosya yüklendiyse işle
    if uploaded_file is not None:
        st.markdown("---")

        # Dosya bilgileri
        file_info_col1, file_info_col2, file_info_col3 = st.columns(3)

        with file_info_col1:
            st.metric("📄 File Name", uploaded_file.name)

        with file_info_col2:
            file_size = uploaded_file.size / 1024  # KB
            if file_size > 1024:
                size_str = f"{file_size / 1024:.1f} MB"
            else:
                size_str = f"{file_size:.1f} KB"
            st.metric("📊 File Size", size_str)

        with file_info_col3:
            st.metric("🕒 Upload Time", datetime.now().strftime("%H:%M:%S"))

        # Dönüştürme butonu
        if st.button("🔄 Convert to JSON", type="primary", use_container_width=True):

            with st.spinner("Converting..."):
                # CSV'yi JSON'a dönüştür
                json_data, error = convert_csv_to_json(uploaded_file)

                if error:
                    st.error(f"❌ Error: {error}")
                else:
                    st.success(f"✅ Conversion successful! {len(json_data)} records processed.")

                    # Sonuç bilgileri
                    result_col1, result_col2 = st.columns(2)

                    with result_col1:
                        st.metric("📋 Total Records", len(json_data))

                    with result_col2:
                        if json_data:
                            field_count = len(json_data[0].keys()) if json_data else 0
                            st.metric("📝 Field Count", field_count)

                    # İlk kayıt önizlemesi
                    if json_data:
                        st.markdown("### 👀 First Record Preview")

                        preview_data = json_data[0]
                        preview_items = list(preview_data.items())[:10]  # İlk 10 alan

                        for key, value in preview_items:
                            if value is not None:
                                st.text(f"{key}: {value}")

                        if len(preview_data) > 10:
                            st.info(f"... and {len(preview_data) - 10} more fields")

                    # JSON dosyası oluştur ve indirme linki
                    json_string = json.dumps(json_data, ensure_ascii=False, indent=2)

                    # Dosya adını oluştur
                    original_name = os.path.splitext(uploaded_file.name)[0]
                    json_filename = f"{original_name}_converted.json"

                    # İndirme butonu
                    st.download_button(
                        label="💾 Download JSON File",
                        data=json_string,
                        file_name=json_filename,
                        mime="application/json",
                        type="primary",
                        use_container_width=True
                    )

                    # Gizlilik uyarısı
                    st.warning(
                        "🔒 Privacy: After downloading the JSON file, the page will refresh to clear the data.")

                    # Temizleme butonu
                    if st.button("🗑️ Clear Data and Refresh Page", type="secondary", use_container_width=True):
                        st.rerun()

    # Alt bilgi
    st.markdown("---")
    st.markdown("""
    <div style='text-align: center; color: #666;'>
    🔒 <strong>Privacy Guarantee:</strong> Uploaded files are not stored on the server. 
    All processing is done in temporary memory and deleted when the page is refreshed.
    </div>
    """, unsafe_allow_html=True)

if __name__ == "__main__":
    main()