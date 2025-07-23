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
        if total_size < 1024 * 1024:  # Under 1MB
            size_display = f"{total_size / 1024:.1f} KB"
        else:
            size_display = f"{total_size / (1024 * 1024):.1f} MB"

        col1, col2, col3, col4 = st.columns(4)

        with col1:
            st.metric("📄 Files Selected", len(uploaded_files))
        with col2:
            st.metric("📊 Total Size", size_display)
        with col3:
            st.metric("🕒 Upload Time", datetime.now().strftime("%H:%M:%S"))
        with col4:
            st.metric("🔄 Status", "Ready to Convert")

        # File list preview
        with st.expander("🔍 File List Preview"):
            total_preview_size = 0
            for i, file in enumerate(uploaded_files, 1):
                file_size = format_file_size(file.size)
                total_preview_size += file.size
                st.write(f"{i}. **{file.name}** ({file_size})")

            # Total size info
            total_size_display = format_file_size(total_preview_size)
            st.info(f"📊 Total size: {total_size_display}")

        # Processing Options
        st.markdown("### ⚙️ Processing Options")

        col1, col2 = st.columns(2)

        with col1:
            auto_transfer = st.checkbox(
                "🚀 Auto-transfer to Order Matcher",
                value=True,
                help="Automatically send converted files to Order Matcher"
            )

        with col2:
            download_files = st.checkbox(
                "💾 Download converted files",
                value=False,
                help="Download all converted JSON files individually"
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
                                # File metrics
                                try:
                                    data = json.loads(json_data)
                                    record_count = len(data)
                                    file_size = format_file_size(len(json_data.encode('utf-8')))
                                    st.success(f"✅ Converted successfully: {record_count} records, {file_size}")

                                    # Preview first record (simplified)
                                    if data:
                                        st.markdown("**Sample Record:**")
                                        preview_data = data[0]
                                        preview_items = list(preview_data.items())[:3]  # Only 3 fields
                                        for key, value in preview_items:
                                            if value is not None:
                                                st.text(f"{key}: {value}")
                                        if len(preview_data) > 3:
                                            st.caption(f"... and {len(preview_data) - 3} more fields")

                                except Exception as e:
                                    st.error(f"❌ JSON parsing error: {e}")

                            except Exception as e:
                                st.error(f"❌ JSON parsing error: {e}")

                # 🆕 BATCH DOWNLOAD OPTIONS
                # Individual Downloads (if requested)
                if successful and download_files:
                    st.markdown("---")
                    st.markdown("### 📄 Download Files")

                    for original_name, json_filename, json_data, error in processed_files:
                        if not error:  # Only successful files
                            file_size = format_file_size(len(json_data.encode('utf-8')))
                            st.download_button(
                                label=f"📄 {json_filename} ({file_size})",
                                data=json_data,
                                file_name=json_filename,
                                mime="application/json",
                                key=f"individual_download_{json_filename}",
                                use_container_width=True
                            )

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
                # Calculate file size
                file_size_bytes = len(json.dumps(file_info['data']).encode('utf-8'))
                file_size = format_file_size(file_size_bytes)
                st.write(f"📄 **{file_info['filename']}** ({len(file_info['data'])} records, {file_size})")
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