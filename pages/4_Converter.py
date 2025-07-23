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


def create_zip_download(processed_files: List[Tuple]) -> bytes:
    """Birden fazla JSON dosyasını ZIP içinde topla"""
    zip_buffer = io.BytesIO()

    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
        for original_name, json_filename, json_data, error in processed_files:
            if not error:  # Sadece başarılı dönüşümleri ekle
                zip_file.writestr(json_filename, json_data)

    zip_buffer.seek(0)
    return zip_buffer.getvalue()


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
    st.title("🔄 Enhanced Multi-CSV Batch Converter")
    st.markdown("Convert multiple eBay CSV files to JSON format with automatic Order Matcher integration")

    # Ana layout
    col1, col2 = st.columns([2, 1])

    with col1:
        st.markdown("""
        ### 📁 Multi-File Upload
        Upload multiple eBay CSV files for batch processing.
        """)

        # 🆕 MULTI-FILE UPLOAD
        uploaded_files = st.file_uploader(
            "Select Multiple eBay CSV Files",
            type=['csv'],
            help="Select multiple CSV files for batch processing",
            accept_multiple_files=True,  # 🆕 Multi-file support
            key="multi_csv_upload"
        )

    with col2:
        st.markdown("""
        ### ✨ Enhanced Features
        - 🔄 **Multi-CSV Processing**
        - 📦 **Individual JSON Output**  
        - 🚀 **Auto Order Matcher Transfer**
        - 📁 **Batch ZIP Download**
        - 🔒 **Privacy Protected**
        """)

    # 🆕 BATCH PROCESSING SECTION
    if uploaded_files:
        st.markdown("---")

        # File summary
        st.markdown(f"### 📊 Upload Summary")

        total_size = sum(file.size for file in uploaded_files)
        size_mb = total_size / (1024 * 1024)

        col1, col2, col3, col4 = st.columns(4)

        with col1:
            st.metric("📄 Files Selected", len(uploaded_files))
        with col2:
            st.metric("📊 Total Size", f"{size_mb:.2f} MB")
        with col3:
            st.metric("🕒 Upload Time", datetime.now().strftime("%H:%M:%S"))
        with col4:
            st.metric("🔄 Status", "Ready to Convert")

        # File list preview
        with st.expander("🔍 File List Preview"):
            for i, file in enumerate(uploaded_files, 1):
                file_size_kb = file.size / 1024
                st.write(f"{i}. **{file.name}** ({file_size_kb:.1f} KB)")

        # 🆕 PROCESSING OPTIONS
        st.markdown("### ⚙️ Processing Options")

        col1, col2 = st.columns(2)

        with col1:
            auto_transfer = st.checkbox(
                "🚀 Auto-transfer to Order Matcher",
                value=True,
                help="Automatically send converted files to Order Matcher upload area"
            )

        with col2:
            create_zip = st.checkbox(
                "📦 Create ZIP download",
                value=True,
                help="Package all converted files into a single ZIP file"
            )

        # 🆕 BATCH CONVERT BUTTON
        if st.button("🔄 Convert All Files to JSON", type="primary", use_container_width=True):

            with st.spinner("🔄 Processing multiple CSV files..."):

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

                # Show conversion results
                st.markdown("### 📊 Conversion Results")

                for original_name, json_filename, json_data, error in processed_files:

                    with st.expander(f"📄 {original_name} → {json_filename}"):

                        if error:
                            st.error(f"❌ {error}")
                        else:
                            # Success info
                            try:
                                data = json.loads(json_data)
                                record_count = len(data)
                                st.success(f"✅ Converted successfully: {record_count} records")

                                # Preview first record
                                if data:
                                    st.markdown("**First Record Preview:**")
                                    preview_data = data[0]
                                    preview_items = list(preview_data.items())[:5]

                                    for key, value in preview_items:
                                        if value is not None:
                                            st.text(f"{key}: {value}")

                                    if len(preview_data) > 5:
                                        st.info(f"... and {len(preview_data) - 5} more fields")

                                # Individual download button
                                st.download_button(
                                    label=f"💾 Download {json_filename}",
                                    data=json_data,
                                    file_name=json_filename,
                                    mime="application/json",
                                    key=f"download_{json_filename}"
                                )

                            except Exception as e:
                                st.error(f"❌ JSON parsing error: {e}")

                # 🆕 BATCH DOWNLOAD OPTIONS
                if successful:
                    st.markdown("---")
                    st.markdown("### 📦 Batch Download Options")

                    col1, col2 = st.columns(2)

                    with col1:
                        # ZIP Download
                        if create_zip:
                            zip_data = create_zip_download(processed_files)
                            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                            zip_filename = f"converted_ebay_files_{timestamp}.zip"

                            st.download_button(
                                label="📦 Download All as ZIP",
                                data=zip_data,
                                file_name=zip_filename,
                                mime="application/zip",
                                type="primary",
                                use_container_width=True
                            )

                    with col2:
                        # Individual files download info
                        st.info(f"📄 {len(successful)} individual JSON files ready for download above")

                # 🆕 AUTO-TRANSFER TO ORDER MATCHER
                if auto_transfer and successful:
                    st.markdown("---")
                    st.markdown("### 🚀 Auto-Transfer to Order Matcher")

                    transferred_count = auto_transfer_to_order_matcher(processed_files)

                    if transferred_count > 0:
                        st.success(f"✅ {transferred_count} files automatically transferred to Order Matcher!")
                        st.info("📍 Go to Order Matcher page to see the pre-loaded files.")

                        # Quick navigation button
                        if st.button("🔗 Go to Order Matcher", type="secondary", use_container_width=True):
                            st.switch_page("pages/2_Order_Matcher.py")
                    else:
                        st.warning("⚠️ No files were transferred (all had errors)")

                # Show failed conversions if any
                if failed:
                    st.markdown("---")
                    st.markdown("### ❌ Failed Conversions")

                    for original_name, _, _, error in failed:
                        st.error(f"**{original_name}**: {error}")

                # 🆕 CLEANUP OPTIONS
                st.markdown("---")
                col1, col2 = st.columns(2)

                with col1:
                    if st.button("🗑️ Clear All Data", type="secondary", use_container_width=True):
                        # Clear session state
                        if 'converted_ebay_files' in st.session_state:
                            del st.session_state.converted_ebay_files
                        st.rerun()

                with col2:
                    if st.button("🔄 Convert More Files", type="secondary", use_container_width=True):
                        st.rerun()

    # 🆕 SHOW PRE-LOADED FILES (if any exist from previous conversions)
    if 'converted_ebay_files' in st.session_state and st.session_state.converted_ebay_files:
        st.markdown("---")
        st.markdown("### 📋 Previously Converted Files (Ready for Order Matcher)")

        converted_files = st.session_state.converted_ebay_files

        st.info(f"📊 {len(converted_files)} files ready for Order Matcher transfer")

        # Show list of converted files
        for i, file_info in enumerate(converted_files):
            col1, col2, col3 = st.columns([2, 1, 1])

            with col1:
                st.write(f"📄 **{file_info['filename']}** ({len(file_info['data'])} records)")
            with col2:
                st.caption(f"Converted: {file_info['converted_at']}")
            with col3:
                if st.button(f"🗑️", key=f"remove_{i}", help="Remove from list"):
                    st.session_state.converted_ebay_files.pop(i)
                    st.rerun()

        # Quick transfer option
        col1, col2 = st.columns(2)

        with col1:
            if st.button("🚀 Transfer All to Order Matcher", type="primary", use_container_width=True):
                st.switch_page("pages/2_Order_Matcher.py")

        with col2:
            if st.button("🗑️ Clear All Converted Files", type="secondary", use_container_width=True):
                st.session_state.converted_ebay_files = []
                st.rerun()

    # 🆕 USAGE INSTRUCTIONS
    with st.expander("📖 How to Use Multi-CSV Batch Converter"):
        st.markdown("""
        **Step-by-Step Guide:**

        1. **📁 Upload Multiple CSV Files**: Select all your eBay CSV files at once
        2. **⚙️ Choose Options**: 
           - ✅ Auto-transfer to Order Matcher (recommended)
           - 📦 Create ZIP download (optional)
        3. **🔄 Convert**: Click "Convert All Files to JSON"
        4. **📦 Download**: 
           - Individual JSON files from each section
           - Or download all as ZIP file
        5. **🚀 Auto-Transfer**: Converted files automatically appear in Order Matcher
        6. **🔗 Continue**: Go to Order Matcher to process your orders

        **Features:**
        - ✅ **Batch Processing**: Convert multiple CSV files simultaneously
        - ✅ **Individual Output**: Each CSV becomes a separate JSON file  
        - ✅ **Automatic Integration**: Files directly transfer to Order Matcher
        - ✅ **Error Handling**: Clear feedback on successful/failed conversions
        - ✅ **ZIP Download**: Package all converted files together
        - ✅ **Session Memory**: Previously converted files remain available
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