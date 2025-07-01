import streamlit as st
import os
import sys

# Path ayarı
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils.pocketbase_client import get_all_data, test_pocketbase_connection

# Sayfa konfigürasyonu
st.set_page_config(
    page_title="Settings",
    page_icon="⚙️",
    layout="wide"
)

st.title("⚙️ System Settings")


def show_connection_settings():
    """PocketBase bağlantı ayarları"""
    st.subheader("🔗 PocketBase Connection Settings")

    # Mevcut ayarları göster
    pocketbase_url = os.getenv('POCKETBASE_URL', 'Not configured')
    collection_name = os.getenv('POCKETBASE_COLLECTION', 'Not configured')
    auth_token = os.getenv('POCKETBASE_TOKEN', 'Not configured')

    col1, col2 = st.columns(2)

    with col1:
        st.info(f"🌐 **URL:** {pocketbase_url}")
        st.info(f"📁 **Collection:** {collection_name}")

    with col2:
        # Token'ı gizle
        token_display = f"{auth_token[:10]}..." if len(auth_token) > 10 else auth_token
        st.info(f"🔐 **Token:** {token_display}")

    st.markdown("---")

    # Bağlantı testi
    st.write("**🔍 Connection Test:**")

    col1, col2 = st.columns([1, 3])

    with col1:
        if st.button("🔍 Test Connection", type="primary"):
            with st.spinner("Testing connection..."):
                try:
                    success, message = test_pocketbase_connection()

                    if success:
                        st.success(f"✅ {message}")

                        # Collection'daki kayıt sayısını göster
                        data = get_all_data()
                        if data:
                            st.info(f"📊 Found {len(data)} records in collection")
                        else:
                            st.warning("📊 Collection is empty")
                    else:
                        st.error(f"❌ {message}")

                except Exception as e:
                    st.error(f"❌ Connection error: {str(e)}")

    with col2:
        if st.button("📁 Go to Data Management"):
            st.switch_page("pages/3_Data_Management.py")


def show_cache_management():
    """Cache yönetimi"""
    st.subheader("🗂️ Cache Management")

    st.write("""
    **What is Cache?**

    Cache stores data temporarily for faster access. 
    Sometimes old data is displayed, in which case cache needs to be cleared.
    """)

    col1, col2 = st.columns(2)

    with col1:
        st.write("**🗑️ Clear Cache:**")
        if st.button("🗑️ Clear Cache", type="secondary"):
            st.cache_data.clear()
            st.success("✅ Cache cleared!")
            st.info("Data will be reloaded.")

    with col2:
        st.write("**🔄 Refresh Application:**")
        if st.button("🔄 Refresh App", type="secondary"):
            st.rerun()

    st.markdown("---")

    # Cache durumu
    st.write("**📊 Cache Status:**")

    try:
        data = get_all_data()
        if data:
            st.success(f"✅ {len(data)} records in cache")
        else:
            st.warning("⚠️ No data in cache or empty")
    except Exception as e:
        st.error(f"❌ Cache check error: {str(e)}")


def show_system_info():
    """Sistem bilgileri"""
    st.subheader("ℹ️ System Information")

    # Uygulama bilgileri
    st.write("**📱 Application:**")
    col1, col2 = st.columns(2)

    with col1:
        st.info("🏢 **Application:** Business Analytics")
        st.info("📊 **Framework:** Streamlit")
        st.info("🗄️ **Database:** PocketBase")

    with col2:
        st.info("🐍 **Python:** " + sys.version.split()[0])
        st.info("💻 **Platform:** " + sys.platform)

    st.markdown("---")

    # Sayfa bilgileri
    st.write("**📄 Available Pages:**")

    pages = [
        "📊 Dashboard - Main metrics and charts",
        "📁 Data Management - Data upload and management",
        "🔗 Order Matcher - eBay-Amazon order matching",
        "🔄 Converter - CSV to JSON conversion",
        "⚙️ Settings - System settings and cache management"
    ]

    for page in pages:
        st.write(f"• {page}")

    st.markdown("---")

    # Hızlı navigasyon
    st.write("**🚀 Quick Navigation:**")

    col1, col2, col3 = st.columns(3)

    with col1:
        if st.button("📊 Go to Dashboard", use_container_width=True):
            st.switch_page("a.py")

    with col2:
        if st.button("📁 Data Management", use_container_width=True):
            st.switch_page("pages/3_Data_Management.py")

    with col3:
        if st.button("🔗 Order Matcher", use_container_width=True):
            st.switch_page("pages/2_Order_Matcher.py")

    st.markdown("---")

    # Environment variables
    st.write("**🔧 Environment Variables:**")

    env_vars = {
        "POCKETBASE_URL": os.getenv('POCKETBASE_URL', 'Not configured'),
        "POCKETBASE_COLLECTION": os.getenv('POCKETBASE_COLLECTION', 'Not configured'),
        "POCKETBASE_TOKEN": "***" if os.getenv('POCKETBASE_TOKEN') else 'Not configured'
    }

    for key, value in env_vars.items():
        st.code(f"{key} = {value}")

    # Debug bilgileri
    with st.expander("🐛 Debug Information"):
        st.write("**Python Path:**")
        for path in sys.path[:5]:  # İlk 5 path'i göster
            st.code(path)

        st.write("**Environment Variables (PocketBase related):**")
        for key, value in os.environ.items():
            if 'POCKETBASE' in key:
                display_value = "***" if 'TOKEN' in key else value
                st.code(f"{key} = {display_value}")


# Tab'lar
tab1, tab2, tab3 = st.tabs(["🔗 Connection", "🗂️ Cache", "ℹ️ System Info"])

with tab1:
    show_connection_settings()

with tab2:
    show_cache_management()

with tab3:
    show_system_info()