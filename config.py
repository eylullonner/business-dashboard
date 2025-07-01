import os
from dotenv import load_dotenv

# .env dosyasını yükle
load_dotenv()

# PocketBase ayarları
POCKETBASE_URL = os.getenv("POCKETBASE_URL", "http://127.0.0.1:8090")
COLLECTION_NAME = os.getenv("POCKETBASE_COLLECTION", "matched_orders")
POCKETBASE_TOKEN = os.getenv("POCKETBASE_TOKEN")

# Streamlit sayfa ayarları
PAGE_CONFIG = {
    "page_title": "📊 Business Dashboard",
    "layout": "wide",
    "initial_sidebar_state": "expanded"
}

# Tarih kolonları
DATE_COLUMNS = {
    "amazon": "amazon_order_placed",
    "ebay": "ebay_order_creation_date"
}

# Numeric alanlar
NUMERIC_FIELDS = [
    'calculated_profit_usd',
    'calculated_amazon_cost_usd',
    'calculated_ebay_earning_usd'
]

# Kolon görüntüleme isimleri
COLUMN_DISPLAY_NAMES = {
    'master_no': 'Master No',
    'ebay_item_title': 'eBay Product',
    'amazon_item_title': 'Amazon Product',
    'calculated_profit_usd': 'Profit ($)',
    'calculated_amazon_cost_usd': 'Amazon Cost ($)',
    'calculated_ebay_earning_usd': 'eBay Revenue ($)',
    'ebay_order_number': 'eBay Order',
    'amazon_order_number': 'Amazon Order',
    'ebay_buyer_name': 'eBay Buyer',
    'amazon_asin': 'Amazon ASIN'
}

# Gizlenecek kolonlar
EXCLUDED_COLUMNS = [
    'id', 'collectionId', 'collectionName',
    'created', 'updated', 'user_id'
]

# Cache ayarları
CACHE_TTL = 300  # 5 dakika

# Pagination ayarları
DEFAULT_PAGE_SIZE = 25
MAX_PAGE_SIZE = 100