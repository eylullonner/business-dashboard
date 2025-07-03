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

# Kolon görüntüleme isimleri - UPDATED: Amazon account support
COLUMN_DISPLAY_NAMES = {
    'master_no': 'Master No',
    'amazon_account': 'Amazon Account',  # YENİ EKLENEN
    'ebay_item_title': 'eBay Product',
    'amazon_item_title': 'Amazon Product',
    'amazon_product_title': 'Amazon Product',  # Alternative field name
    'calculated_profit_usd': 'Profit ($)',
    'calculated_amazon_cost_usd': 'Amazon Cost ($)',
    'calculated_ebay_earning_usd': 'eBay Revenue ($)',
    'ebay_order_number': 'eBay Order',
    'amazon_order_number': 'Amazon Order',
    'amazon_orderid': 'Amazon Order ID',  # Alternative field name
    'ebay_buyer_name': 'eBay Buyer',
    'amazon_asin': 'Amazon ASIN',
    'amazon_product_url': 'Amazon URL',
    'amazon_ship_to': 'Amazon Ship To',
    'calculated_margin_percent': 'Margin (%)',
    'calculated_roi_percent': 'ROI (%)',
    'exchange_rate_used': 'Exchange Rate',
    'cost_calculation_method': 'Cost Method'
}

# Gizlenecek kolonlar - UPDATED: Amazon account preserved
EXCLUDED_COLUMNS = [
    'id', 'collectionId', 'collectionName',
    'created', 'updated', 'user_id'
]

# Priority columns for display - UPDATED: Amazon account high priority
PRIORITY_DISPLAY_COLUMNS = [
    'master_no',
    'amazon_account',  # YENİ EKLENEN - Priority 2
    'ebay_order_number',
    'amazon_orderid',
    'calculated_profit_usd',
    'calculated_amazon_cost_usd',
    'calculated_ebay_earning_usd',
    'ebay_item_title',
    'amazon_product_title',
    'amazon_asin'
]

# Account related settings - YENİ BÖLÜM
ACCOUNT_SETTINGS = {
    'default_account_name': 'unknown',
    'account_field_name': 'amazon_account',
    'account_extraction_separator': '_',  # buyer1_amazon.json -> buyer1
    'max_accounts_display': 10,
    'account_color_palette': [
        '#FF6B6B', '#4ECDC4', '#45B7D1', '#96CEB4', '#FFEAA7',
        '#DDA0DD', '#98D8C8', '#F7DC6F', '#BB8FCE', '#85C1E9'
    ]
}

# Account filtering and grouping
ACCOUNT_FILTER_OPTIONS = {
    'all_accounts': 'All Accounts',
    'specific_account': 'Specific Account',
    'account_comparison': 'Account Comparison',
    'top_performing': 'Top Performing Accounts'
}

# Cache ayarları
CACHE_TTL = 300  # 5 dakika

# Pagination ayarları
DEFAULT_PAGE_SIZE = 25
MAX_PAGE_SIZE = 100

# Multi-account processing settings - YENİ BÖLÜM
MULTI_ACCOUNT_CONFIG = {
    'max_concurrent_files': 10,
    'supported_file_formats': ['.json'],
    'filename_patterns': {
        'account_prefix': r'^([a-zA-Z0-9_-]+)_',  # buyer1_amazon.json
        'account_suffix': r'_([a-zA-Z0-9_-]+)\.json$'  # amazon_buyer1.json
    },
    'validation': {
        'min_account_name_length': 2,
        'max_account_name_length': 50,
        'allowed_account_chars': r'^[a-zA-Z0-9_-]+$'
    }
}

# Dashboard visualization settings for accounts - YENİ BÖLÜM
ACCOUNT_VISUALIZATION = {
    'chart_types': {
        'profit_by_account': 'bar',
        'order_count_by_account': 'pie',
        'roi_comparison': 'line',
        'cost_distribution': 'histogram'
    },
    'default_metrics': [
        'total_orders',
        'total_profit',
        'average_profit',
        'roi_percentage',
        'profitable_orders_ratio'
    ],
    'color_scheme': 'Set3'  # Plotly color scheme
}

# Business metrics calculation - UPDATED for multi-account
BUSINESS_METRICS = {
    'profit_thresholds': {
        'excellent': 50.0,  # $50+ profit per order
        'good': 25.0,  # $25+ profit per order
        'fair': 10.0,  # $10+ profit per order
        'poor': 0.0  # Break-even or loss
    },
    'roi_thresholds': {
        'excellent': 30.0,  # 30%+ ROI
        'good': 20.0,  # 20%+ ROI
        'fair': 10.0,  # 10%+ ROI
        'poor': 0.0  # Break-even or loss
    },
    'margin_thresholds': {
        'excellent': 20.0,  # 20%+ margin
        'good': 15.0,  # 15%+ margin
        'fair': 10.0,  # 10%+ margin
        'poor': 0.0  # Break-even or loss
    }
}

# Account performance ratings - YENİ BÖLÜM
ACCOUNT_PERFORMANCE_CONFIG = {
    'rating_criteria': {
        'total_profit': 0.4,  # 40% weight
        'average_roi': 0.3,  # 30% weight
        'order_count': 0.2,  # 20% weight
        'success_rate': 0.1  # 10% weight
    },
    'performance_levels': {
        'A+': {'min_score': 90, 'label': 'Excellent', 'color': '#2ECC71'},
        'A': {'min_score': 80, 'label': 'Very Good', 'color': '#27AE60'},
        'B+': {'min_score': 70, 'label': 'Good', 'color': '#F39C12'},
        'B': {'min_score': 60, 'label': 'Fair', 'color': '#E67E22'},
        'C': {'min_score': 50, 'label': 'Below Average', 'color': '#E74C3C'},
        'D': {'min_score': 0, 'label': 'Poor', 'color': '#C0392B'}
    }
}

# Data export settings for multi-account - YENİ BÖLÜM
EXPORT_CONFIG = {
    'filename_templates': {
        'single_account': 'matched_orders_{account}_{timestamp}.{format}',
        'multi_account': 'matched_orders_multi_account_{timestamp}.{format}',
        'account_summary': 'account_summary_{timestamp}.{format}'
    },
    'supported_formats': ['json', 'csv', 'xlsx'],
    'include_account_sheets': True,  # Excel için ayrı sheet'ler
    'default_format': 'json'
}

# Error handling and validation for accounts - YENİ BÖLÜM
ACCOUNT_VALIDATION = {
    'required_fields_per_account': [
        'amazon_orderid',
        'amazon_account'
    ],
    'duplicate_handling': 'composite_key',  # amazon_orderid + amazon_account
    'missing_account_behavior': 'assign_default',  # 'assign_default' or 'reject'
    'invalid_account_behavior': 'sanitize'  # 'sanitize' or 'reject'
}

# UI/UX settings for account features - YENİ BÖLÜM
ACCOUNT_UI_CONFIG = {
    'show_account_in_table': True,
    'account_column_position': 2,  # 2nd column after master_no
    'enable_account_filtering': True,
    'enable_account_grouping': True,
    'show_account_metrics': True,
    'account_badges': True,  # Show colored badges for accounts
    'account_search': True  # Enable account search/autocomplete
}

# Logging and debugging for multi-account - YENİ BÖLÜM
DEBUG_CONFIG = {
    'log_account_processing': True,
    'log_duplicate_detection': True,
    'log_matching_decisions': True,
    'verbose_account_extraction': True,
    'track_processing_time_per_account': True
}

# Backward compatibility settings - YENİ BÖLÜM
COMPATIBILITY = {
    'support_legacy_data': True,  # Support data without amazon_account field
    'legacy_account_name': 'legacy',  # Default name for old records
    'migrate_legacy_data': False,  # Auto-migrate old data
    'warn_missing_account': True  # Show warnings for missing account info
}

# File upload constraints for multi-account - YENİ BÖLÜM
UPLOAD_CONSTRAINTS = {
    'max_file_size_mb': 50,
    'max_files_per_upload': 10,
    'max_total_size_mb': 200,
    'allowed_file_extensions': ['.json'],
    'require_account_in_filename': False,  # If True, filename must contain account info
    'auto_detect_account_from_filename': True
}

# Performance monitoring for accounts - YENİ BÖLÜM
PERFORMANCE_MONITORING = {
    'track_account_processing_time': True,
    'benchmark_against_single_account': True,
    'alert_slow_accounts': True,
    'slow_account_threshold_seconds': 30,
    'memory_usage_tracking': True
}

# Integration settings - YENİ BÖLÜM
INTEGRATION_CONFIG = {
    'enable_account_based_api_calls': True,
    'rate_limit_per_account': True,
    'separate_exchange_rate_cache_per_account': False,
    'account_specific_error_handling': True
}

# Feature flags for gradual rollout - YENİ BÖLÜM
FEATURE_FLAGS = {
    'enable_multi_account': True,
    'enable_account_performance_rating': True,
    'enable_account_comparison_charts': True,
    'enable_account_based_filtering': True,
    'enable_account_export_options': True,
    'enable_account_migration_tools': True,
    'enable_composite_key_validation': True
}


# Helper functions for account configuration - YENİ BÖLÜM
def get_account_color(account_name, account_index=0):
    """Get consistent color for account"""
    colors = ACCOUNT_SETTINGS['account_color_palette']
    return colors[account_index % len(colors)]


def validate_account_name(account_name):
    """Validate account name format"""
    import re
    pattern = MULTI_ACCOUNT_CONFIG['validation']['allowed_account_chars']
    min_len = MULTI_ACCOUNT_CONFIG['validation']['min_account_name_length']
    max_len = MULTI_ACCOUNT_CONFIG['validation']['max_account_name_length']

    if not account_name or len(account_name) < min_len or len(account_name) > max_len:
        return False

    return bool(re.match(pattern, account_name))


def get_performance_rating(score):
    """Get performance rating based on score"""
    for rating, config in ACCOUNT_PERFORMANCE_CONFIG['performance_levels'].items():
        if score >= config['min_score']:
            return rating, config['label'], config['color']
    return 'D', 'Poor', '#C0392B'


def should_enable_feature(feature_name):
    """Check if feature is enabled"""
    return FEATURE_FLAGS.get(feature_name, False)


# Export commonly used configurations
COMMON_CONFIGS = {
    'display_columns': PRIORITY_DISPLAY_COLUMNS,
    'account_settings': ACCOUNT_SETTINGS,
    'export_config': EXPORT_CONFIG,
    'validation': ACCOUNT_VALIDATION
}