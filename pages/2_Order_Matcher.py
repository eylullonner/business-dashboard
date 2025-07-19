import streamlit as st
import pandas as pd
import json
import re
from datetime import datetime
from typing import Dict, List, Tuple, Optional
import warnings
import sys
import os

# DEPLOY-SAFE IMPORT - Hem local hem Streamlit Cloud için
try:
    # Streamlit Cloud path
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from utils.international_matcher import InternationalMatcher
    from utils.debug_analyzer import AccountSeparatedDebugAnalyzer
    from utils.data_processor import calculate_single_order_profit
    print("✅ Utils imported successfully (Streamlit Cloud path)")
except ImportError:
    try:
        # Local development path
        import sys
        import os
        sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
        from utils.international_matcher import InternationalMatcher
        from utils.debug_analyzer import AccountSeparatedDebugAnalyzer
        from utils.data_processor import calculate_single_order_profit
        print("✅ Utils imported successfully (Local path)")
    except ImportError as e:
        st.error(f"❌ Import error: {e}")
        st.error("Please check if utils folder is in the correct location")
        st.stop()

# Enhanced name matching import - FALLBACK approach
try:
    from utils.data_processor import enhanced_fuzzy_name_match
    ENHANCED_MATCHING_AVAILABLE = True
    print("✅ Enhanced name matching imported")
except ImportError:
    ENHANCED_MATCHING_AVAILABLE = False
    print("⚠️ Enhanced name matching not available - using fallback")

# Diğer import'lar
try:
    from fuzzywuzzy import fuzz
    FUZZYWUZZY_AVAILABLE = True
except ImportError:
    FUZZYWUZZY_AVAILABLE = False

try:
    import plotly.express as px
    PLOTLY_AVAILABLE = True
except ImportError:
    PLOTLY_AVAILABLE = False

try:
    from dateutil import parser as date_parser
    DATEUTIL_AVAILABLE = True
except ImportError:
    DATEUTIL_AVAILABLE = False

warnings.filterwarnings('ignore')

# Sayfa konfigürasyonu
st.set_page_config(
    page_title="Order Matcher",
    page_icon="🔗",
    layout="wide"
)

st.title("🔗 Order Matcher")
st.markdown("Match eBay and Amazon orders and calculate profit metrics")

# Kütüphane kontrolü
if not FUZZYWUZZY_AVAILABLE:
    st.error("❌ fuzzywuzzy library not found!")
    st.code("pip install fuzzywuzzy python-Levenshtein")
    st.stop()

if not PLOTLY_AVAILABLE:
    st.warning("⚠️ plotly library not found. Charts will not be displayed.")


class DropshippingMatcher:
    """eBay ve Amazon siparişlerini eşleştiren ve kâr hesaplayan sınıf"""

    def __init__(self, threshold: float = 70):
        self.weights = {
            'name': 0.30,
            'zip': 0.25,
            'title': 0.25,
            'city': 0.12,
            'state': 0.08
        }
        self.threshold = threshold
        self.international_matcher = InternationalMatcher()

    # ========== UTILITY FUNCTIONS ==========

    def find_best_match_in_address_enhanced(self, search_term: str, address: str) -> int:
        """
        Geliştirilmiş adres içinde isim arama
        """
        if not search_term or not address:
            return 0

        from utils.data_processor import enhanced_fuzzy_name_match

        search_clean = search_term.lower().strip()
        address_clean = address.lower().strip()

        # Tam substring kontrolü
        if search_clean in address_clean:
            return 100

        # Adres kelimelerini parse et
        address_words = re.split(r'[^\w]+', address_clean)
        best_score = 0

        for word in address_words:
            if word and len(word) >= 2:
                score = enhanced_fuzzy_name_match(search_term, word)
                if score > best_score:
                    best_score = score

        return best_score
    def parse_date(self, date_str: str) -> Optional[datetime]:
        """Tarih string'ini datetime objesine çevir"""
        if not date_str or pd.isna(date_str):
            return None

        date_str = str(date_str).strip()

        # Yaygın tarih formatları
        date_formats = [
            '%Y-%m-%d', '%m/%d/%Y', '%d/%m/%Y', '%Y/%m/%d',
            '%B %d, %Y', '%b %d, %Y', '%d %B %Y', '%d %b %Y',
            '%Y-%m-%d %H:%M:%S', '%m/%d/%Y %H:%M:%S'
        ]

        for date_format in date_formats:
            try:
                return datetime.strptime(date_str, date_format)
            except ValueError:
                continue

        # dateutil parser (daha esnek)
        if DATEUTIL_AVAILABLE:
            try:
                return date_parser.parse(date_str)
            except:
                pass

        return None

    def check_date_logic(self, ebay_date: str, amazon_date: str) -> Tuple[bool, str, int]:
        """Tarih mantığı kontrolü: Amazon >= eBay olmalı"""
        ebay_dt = self.parse_date(ebay_date)
        amazon_dt = self.parse_date(amazon_date)

        if ebay_dt is None or amazon_dt is None:
            return True, "date_skip", 0

        days_diff = (amazon_dt - ebay_dt).days

        if amazon_dt < ebay_dt:
            return False, "date_invalid", days_diff

        return True, "date_valid", days_diff

    def standardize_product_terms(self, title: str) -> str:
        """Ürün terimlerini standartlaştır"""
        if not title:
            return ""

        standardizations = {
            r'\b(\d+)\s*pack\b': r'\1pack',
            r'\b(\d+)\s*piece\b': r'\1piece',
            r'\b(\d+)\s*set\b': r'\1set',
            r'\b(\d+)\s*ml\b': r'\1ml',
            r'\b(\d+)\s*oz\b': r'\1oz',
            r'\b(\d+)h\b': r'\1h'
        }

        result = title.lower()
        for pattern, replacement in standardizations.items():
            result = re.sub(pattern, replacement, result)

        return result

    def extract_key_words(self, title: str, min_length: int = 2) -> set:
        """Başlıktan anahtar kelimeleri çıkar"""
        if not title:
            return set()

        standardized = self.standardize_product_terms(title)
        standardized = re.sub(r'-', ' ', standardized)
        words = standardized.split()

        stopwords = {
            'a', 'an', 'the', 'and', 'or', 'but', 'in', 'on', 'at', 'is', 'are',
            'item', 'product', 'brand', 'shipping', 'delivery', 'with', 'from'
        }

        key_words = set()
        for word in words:
            clean_word = re.sub(r'[^\w]', '', word)
            if (len(clean_word) >= min_length and
                    clean_word not in stopwords and
                    not clean_word.isdigit() and
                    clean_word.isalnum()):
                key_words.add(clean_word)

        return key_words

    def calculate_title_similarity(self, ebay_title: str, amazon_title: str) -> int:
        """İki ürün başlığı arasındaki benzerliği hesapla"""
        if not ebay_title or not amazon_title:
            return 0

        ebay_std = self.standardize_product_terms(ebay_title)
        amazon_std = self.standardize_product_terms(amazon_title)

        # Çoklu benzerlik yaklaşımları
        direct_score = fuzz.ratio(ebay_std, amazon_std)
        partial_score = fuzz.partial_ratio(ebay_std, amazon_std)
        token_score = fuzz.token_set_ratio(ebay_std, amazon_std)

        # Anahtar kelime bazlı benzerlik
        ebay_keywords = self.extract_key_words(ebay_std)
        amazon_keywords = self.extract_key_words(amazon_std)

        if ebay_keywords and amazon_keywords:
            common_keywords = ebay_keywords.intersection(amazon_keywords)
            union_keywords = ebay_keywords.union(amazon_keywords)
            keyword_score = (len(common_keywords) / len(union_keywords)) * 100
        else:
            keyword_score = 0

        scores = [direct_score, partial_score, token_score, keyword_score]
        return int(max(scores))

    def find_best_match_in_address(self, search_term: str, address: str) -> int:
        """Adres içinde en iyi eşleşmeyi bul"""
        if not search_term or not address:
            return 0

        search_clean = search_term.lower().strip()
        address_clean = address.lower().strip()

        # Tam substring eşleşmesi
        if search_clean in address_clean:
            return 100

        # Kelimeler arası fuzzy eşleştirme
        address_words = re.split(r'[^\w]+', address_clean)
        best_score = 0

        for word in address_words:
            if word and len(word) >= 2:
                score = fuzz.ratio(search_clean, word)
                if score > best_score:
                    best_score = score

                if len(word) > 4:
                    partial_score = fuzz.partial_ratio(search_clean, word)
                    if partial_score > best_score:
                        best_score = partial_score

        return best_score

    def detect_amazon_format(self, amazon_df: pd.DataFrame) -> str:
        """Amazon format'ını tespit et"""
        new_format_columns = ['orderTotal', 'orderDate', 'shippingAddress']
        if any(col in amazon_df.columns for col in new_format_columns):
            return "new"
        old_format_columns = ['grand_total', 'order_date', 'ship_to']
        if any(col in amazon_df.columns for col in old_format_columns):
            return "old"
        return "unknown"
    def match_state(self, ebay_state: str, amazon_address: str) -> int:
        """Eyalet eşleştirmesi (kısaltmalar dahil)"""
        if not ebay_state or not amazon_address:
            return 0

        ebay_clean = ebay_state.lower().strip()
        address_clean = amazon_address.lower()

        # Eyalet kısaltmaları
        state_abbrev = {
            'al': 'alabama', 'ak': 'alaska', 'az': 'arizona', 'ar': 'arkansas', 'ca': 'california',
            'co': 'colorado', 'ct': 'connecticut', 'de': 'delaware', 'fl': 'florida', 'ga': 'georgia',
            'hi': 'hawaii', 'id': 'idaho', 'il': 'illinois', 'in': 'indiana', 'ia': 'iowa',
            'ks': 'kansas', 'ky': 'kentucky', 'la': 'louisiana', 'me': 'maine', 'md': 'maryland',
            'ma': 'massachusetts', 'mi': 'michigan', 'mn': 'minnesota', 'ms': 'mississippi', 'mo': 'missouri',
            'mt': 'montana', 'ne': 'nebraska', 'nv': 'nevada', 'nh': 'new hampshire', 'nj': 'new jersey',
            'nm': 'new mexico', 'ny': 'new york', 'nc': 'north carolina', 'nd': 'north dakota', 'oh': 'ohio',
            'ok': 'oklahoma', 'or': 'oregon', 'pa': 'pennsylvania', 'ri': 'rhode island', 'sc': 'south carolina',
            'sd': 'south dakota', 'tn': 'tennessee', 'tx': 'texas', 'ut': 'utah', 'vt': 'vermont',
            'va': 'virginia', 'wa': 'washington', 'wv': 'west virginia', 'wi': 'wisconsin', 'wy': 'wyoming'
        }

        # Doğrudan eşleşme
        if ebay_clean in address_clean:
            return 100

        # Kısaltma eşleştirmesi
        if ebay_clean in state_abbrev:
            full_name = state_abbrev[ebay_clean]
            if full_name in address_clean:
                return 100

        # Ters kontrol
        for abbrev, full_name in state_abbrev.items():
            if ebay_clean == full_name and abbrev in address_clean:
                return 100

        return 0

    def match_zip_code(self, ebay_zip: str, amazon_address: str) -> int:
        """ZIP kod eşleştirmesi"""
        if not ebay_zip or not amazon_address:
            return 0

        ebay_zip_base = re.findall(r'\d{5}', str(ebay_zip))
        amazon_zips = re.findall(r'\d{5}', amazon_address)

        if not ebay_zip_base:
            return 0

        ebay_base = ebay_zip_base[0]
        for amazon_zip in amazon_zips:
            if ebay_base == amazon_zip:
                return 100

        return 0


    def extract_address_from_shipping_object(self, shipping_address_obj) -> Dict[str, str]:
        """shippingAddress object'inden adres bilgilerini çıkar"""
        if not shipping_address_obj:
            return {}

        # String ise (mixed format)
        if isinstance(shipping_address_obj, str):
            try:
                parsed_obj = json.loads(shipping_address_obj)
                if isinstance(parsed_obj, dict):
                    return self.extract_address_from_shipping_object(parsed_obj)
                else:
                    # Regular string address
                    lines = shipping_address_obj.strip().split('\n')
                    if len(lines) >= 3:
                        return {
                            'name': lines[0].strip(),
                            'address_line': lines[1].strip() if len(lines) > 1 else '',
                            'city_state_zip': lines[2].strip() if len(lines) > 2 else '',
                            'country': lines[3].strip() if len(lines) > 3 else ''
                        }
                    return {}
            except:
                lines = str(shipping_address_obj).strip().split('\n')
                if len(lines) >= 3:
                    return {
                        'name': lines[0].strip(),
                        'address_line': lines[1].strip() if len(lines) > 1 else '',
                        'city_state_zip': lines[2].strip() if len(lines) > 2 else '',
                        'country': lines[3].strip() if len(lines) > 3 else ''
                    }
                return {}

        if not isinstance(shipping_address_obj, dict):
            return {}

        extracted = {}

        # Name extraction
        name_fields = ['name', 'recipient_name', 'buyer_name', 'fullName']
        for field in name_fields:
            if field in shipping_address_obj and shipping_address_obj[field]:
                extracted['name'] = str(shipping_address_obj[field]).strip()
                break

        # Address line extraction
        address_fields = ['addressLine1', 'address_line_1', 'street', 'address1']
        for field in address_fields:
            if field in shipping_address_obj and shipping_address_obj[field]:
                extracted['address_line'] = str(shipping_address_obj[field]).strip()
                break

        # City, State, ZIP extraction
        if 'cityStateZip' in shipping_address_obj:
            city_state_zip = str(shipping_address_obj['cityStateZip']).strip()
            extracted['city_state_zip'] = city_state_zip
            # Parse ayrı ayrı
            match = re.match(r'([^,]+),\s*([A-Z]{2})\s+(\d{5}(?:-\d{4})?)', city_state_zip)
            if match:
                extracted['city'] = match.group(1).strip()
                extracted['state'] = match.group(2).strip()
                extracted['zip'] = match.group(3).strip()
        else:
            # Ayrı field'lar varsa
            if 'city' in shipping_address_obj:
                extracted['city'] = str(shipping_address_obj['city']).strip()
            if 'state' in shipping_address_obj:
                extracted['state'] = str(shipping_address_obj['state']).strip()
            if 'zip' in shipping_address_obj or 'zipCode' in shipping_address_obj:
                zip_code = shipping_address_obj.get('zip') or shipping_address_obj.get('zipCode')
                extracted['zip'] = str(zip_code).strip()

        # Country extraction
        country_fields = ['country', 'countryCode', 'nation']
        for field in country_fields:
            if field in shipping_address_obj and shipping_address_obj[field]:
                extracted['country'] = str(shipping_address_obj[field]).strip()
                break

        return extracted

    def build_full_address_string(self, address_parts: Dict[str, str]) -> str:
        """Address parts'tan tam adres string'i oluştur"""
        address_lines = []

        if 'name' in address_parts and address_parts['name']:
            address_lines.append(address_parts['name'])

        if 'address_line' in address_parts and address_parts['address_line']:
            address_lines.append(address_parts['address_line'])

        if 'city_state_zip' in address_parts and address_parts['city_state_zip']:
            address_lines.append(address_parts['city_state_zip'])
        elif 'city' in address_parts or 'state' in address_parts or 'zip' in address_parts:
            # Parçaları birleştir
            city_state_zip_parts = []
            if 'city' in address_parts and address_parts['city']:
                city_state_zip_parts.append(address_parts['city'])

            state_zip = []
            if 'state' in address_parts and address_parts['state']:
                state_zip.append(address_parts['state'])
            if 'zip' in address_parts and address_parts['zip']:
                state_zip.append(address_parts['zip'])

            if state_zip:
                city_state_zip_parts.append(' '.join(state_zip))

            if city_state_zip_parts:
                address_lines.append(', '.join(city_state_zip_parts))

        if 'country' in address_parts and address_parts['country']:
            address_lines.append(address_parts['country'])

        return '\n'.join(address_lines)

    def normalize_amazon_data_enhanced(self, df: pd.DataFrame) -> pd.DataFrame:
        """Amazon datasını normalize et - Geliştirilmiş address handling"""
        normalized_df = df.copy()
        format_type = self.detect_amazon_format(df)

        for idx, row in normalized_df.iterrows():
            # 1. shippingAddress object'i varsa işle
            if 'shippingAddress' in row and pd.notna(row['shippingAddress']):
                shipping_obj = row['shippingAddress']
                address_parts = self.extract_address_from_shipping_object(shipping_obj)

                if address_parts:
                    full_address = self.build_full_address_string(address_parts)
                    normalized_df.at[idx, 'full_address'] = full_address

                    # Diğer field'ları populate et
                    if 'name' in address_parts:
                        normalized_df.at[idx, 'buyer_name'] = address_parts['name']
                    if 'city' in address_parts:
                        normalized_df.at[idx, 'ship_city'] = address_parts['city']
                    if 'state' in address_parts:
                        normalized_df.at[idx, 'ship_state'] = address_parts['state']
                    if 'zip' in address_parts:
                        normalized_df.at[idx, 'ship_zip'] = address_parts['zip']
                    if 'country' in address_parts:
                        normalized_df.at[idx, 'ship_country'] = address_parts['country']

            # 2. Eski format ship_to field'ı varsa işle
            elif 'ship_to' in row and pd.notna(row['ship_to']):
                normalized_df.at[idx, 'full_address'] = str(row['ship_to'])

            # 3. Yeni format field mapping
            if format_type == "new":
                if 'orderTotal' in row and pd.notna(row['orderTotal']):
                    normalized_df.at[idx, 'grand_total'] = row['orderTotal']
                if 'orderDate' in row and pd.notna(row['orderDate']):
                    normalized_df.at[idx, 'order_date'] = row['orderDate']
                if 'orderNumber' in row and pd.notna(row['orderNumber']):
                    normalized_df.at[idx, 'order_id'] = row['orderNumber']
                if 'itemTitle' in row and pd.notna(row['itemTitle']):
                    normalized_df.at[idx, 'item_title'] = row['itemTitle']

        # Eksik kolonları ekle
        required_columns = [
            'order_id', 'buyer_name', 'ship_city', 'ship_state', 'ship_zip',
            'ship_country', 'item_title', 'order_date', 'order_earning',
            'full_address', 'exchange_rate', 'grand_total', 'amazon_cost_usd'
        ]
        for col in required_columns:
            if col not in normalized_df.columns:
                normalized_df[col] = ""

        return normalized_df

    # ========== MATCHING LOGIC ==========

    def auto_detect_columns(self, df: pd.DataFrame, data_type: str) -> Dict[str, str]:
        """Kolonları otomatik tespit et"""
        if data_type.lower() == 'ebay':
            possible_fields = {
                'order_id': ['Order number', 'order_number', 'orderNumber', 'orderId', 'id'],
                'buyer_name': ['Buyer name', 'buyer_name', 'buyerName', 'recipient_name', 'name'],
                'ship_city': ['Ship to city', 'ship_city', 'city', 'shipping_city'],
                'ship_state': ['Ship to province/region/state', 'ship_state', 'state'],
                'ship_zip': ['Ship to zip', 'ship_zip', 'zip', 'postal_code'],
                'ship_country': ['Ship to country', 'ship_country', 'country'],
                'item_title': ['Item title', 'item_title', 'title', 'product_name'],
                'order_date': ['Order creation date', 'order_date', 'creation_date', 'date'],
                'order_earning': ['Order earnings', 'order_earning', 'earnings', 'profit']
            }
        else:  # amazon
            possible_fields = {
                'order_id': ['order_number', 'Order Number', 'orderNumber', 'orderId', 'id'],
                'full_address': ['ship_to', 'Ship to', 'shipping_address', 'address', 'shippingAddress'],
                'item_title': ['item_title', 'Item title', 'Product title', 'title', 'itemTitle'],
                'order_date': ['order_placed', 'Order placed', 'orderPlaced', 'date', 'orderDate'],
                'exchange_rate': ['exchange_rate', 'Exchange rate', 'rate'],
                'grand_total': ['grand_total', 'Grand total', 'total', 'amount', 'orderTotal'],
                'amazon_cost_usd': ['amazon_cost_usd', 'Amazon cost USD', 'cost_usd', 'cost']
            }

        detected_mapping = {}
        available_columns = df.columns.tolist()

        for standard_field, possible_names in possible_fields.items():
            for possible_name in possible_names:
                if possible_name in available_columns:
                    detected_mapping[standard_field] = possible_name
                    break

        return detected_mapping

    def normalize_data(self, df: pd.DataFrame, column_mapping: Dict[str, str], data_type: str = '') -> pd.DataFrame:
        """Veriyi normalize et"""
        if data_type == 'amazon':
            return self.normalize_amazon_data_enhanced(df)
        else:
            # eBay için mevcut logic
            normalized_df = df.copy()

            # Kolonları yeniden adlandır
            rename_dict = {v: k for k, v in column_mapping.items() if v in df.columns}
            normalized_df = normalized_df.rename(columns=rename_dict)

            # Eksik kolonları ekle
            required_columns = [
                'order_id', 'buyer_name', 'ship_city', 'ship_state', 'ship_zip',
                'ship_country', 'item_title', 'order_date', 'order_earning'
            ]

            for col in required_columns:
                if col not in normalized_df.columns:
                    normalized_df[col] = ""

            return normalized_df

    # 🆕 ENHANCED MATCHING WITH INTERNATIONAL SUPPORT
    def calculate_match_score_with_international(self, ebay_order: Dict, amazon_order: Dict) -> Dict:
        """Enhanced matching with international eIS CO pattern detection"""

        # 🧪 DEBUG: Show ALL eIS CO attempts
        if 'shippingAddress' in amazon_order and 'name' in amazon_order['shippingAddress']:
            amazon_name = amazon_order['shippingAddress']['name']
            if 'eIS CO' in amazon_name:
                ebay_buyer = ebay_order.get('buyer_name', 'N/A')
                ebay_country = ebay_order.get('ship_country', 'N/A')
                print(f"🌍 TRYING eIS CO: Amazon='{amazon_name}' vs eBay='{ebay_buyer}' (Country: {ebay_country})")

        # STEP 1: Try international matching first
        international_result = self.international_matcher.calculate_international_match_score(
            ebay_order,
            amazon_order,
            title_similarity_func=self.calculate_title_similarity,
            date_check_func=self.check_date_logic
        )

        # If international match found, return it
        if international_result['is_match']:
            return international_result

        # STEP 2: Fallback to normal domestic matching
        return self.calculate_match_score_enhanced(ebay_order, amazon_order)

    def calculate_match_score_enhanced(self, ebay_order: Dict, amazon_order: Dict) -> Dict:
        """Eşleştirme skorunu hesapla - Geliştirilmiş address handling"""
        amazon_address = ""

        # 1. Önce full_address field'ına bak
        if 'full_address' in amazon_order and pd.notna(amazon_order['full_address']) and amazon_order['full_address']:
            amazon_address = str(amazon_order['full_address'])

        # 2. full_address yoksa shippingAddress object'inden oluştur
        elif 'shippingAddress' in amazon_order and pd.notna(amazon_order['shippingAddress']):
            shipping_obj = amazon_order['shippingAddress']
            address_parts = self.extract_address_from_shipping_object(shipping_obj)
            if address_parts:
                amazon_address = self.build_full_address_string(address_parts)

        # 3. Son çare: mevcut field'ları birleştir
        else:
            address_parts = [
                str(amazon_order.get('buyer_name', '')),
                str(amazon_order.get('ship_city', '')),
                str(amazon_order.get('ship_state', '')),
                str(amazon_order.get('ship_zip', '')),
                str(amazon_order.get('ship_country', ''))
            ]
            amazon_address = ' '.join([part for part in address_parts if part and part != 'nan'])

        if not amazon_address.strip():
            return {
                'total_score': 0,
                'is_match': False,
                'days_difference': 999,
                'date_status': 'no_address'
            }

        # Adres eşleştirmesi
        name_score = self.find_best_match_in_address_enhanced(
            ebay_order.get('buyer_name', ''), amazon_address)
        city_score = self.find_best_match_in_address(
            ebay_order.get('ship_city', ''), amazon_address)
        state_score = self.match_state(
            ebay_order.get('ship_state', ''), amazon_address)
        zip_score = self.match_zip_code(
            ebay_order.get('ship_zip', ''), amazon_address)

        # Ürün başlığı eşleştirmesi
        title_score = self.calculate_title_similarity(
            ebay_order.get('item_title', ''),
            amazon_order.get('item_title', '')
        )

        # Tarih kontrolü
        date_valid, date_info, days_diff = self.check_date_logic(
            ebay_order.get('order_date', ''),
            amazon_order.get('order_date', '')
        )

        # Ağırlıklı toplam skor
        total_score = (
                name_score * self.weights['name'] +
                city_score * self.weights['city'] +
                state_score * self.weights['state'] +
                zip_score * self.weights['zip'] +
                title_score * self.weights['title']
        )

        # Final karar: threshold ve tarih kontrolü
        is_match = total_score >= self.threshold and date_valid

        return {
            'total_score': round(total_score, 1),
            'is_match': is_match,
            'days_difference': days_diff,
            'date_status': date_info
        }

    # 🔄 UPDATED: Use international matching
    def calculate_match_score(self, ebay_order: Dict, amazon_order: Dict) -> Dict:
        return self.calculate_match_score_with_international(ebay_order, amazon_order)

    # TRY → USD çevirim - Embedded rate olmadan (4 yöntem)


    def extract_account_name_from_filename(self, filename: str) -> str:
        """Dosya isminden Amazon account ismini çıkar"""
        if not filename:
            return "unknown"

        # Dosya uzantısını kaldır
        name_without_ext = filename.rsplit('.', 1)[0]

        # Underscore ile split et ve ilk kısmı al
        parts = name_without_ext.split('_')
        if len(parts) > 1:
            return parts[0]  # "buyer1_amazon.json" -> "buyer1"

        # Eğer underscore yoksa dosya isminin ilk kelimesini al
        first_word = name_without_ext.split()[0] if name_without_ext.split() else name_without_ext
        return first_word

    def combine_amazon_files(self, amazon_files_data: List[Tuple[str, pd.DataFrame]]) -> pd.DataFrame:
        """Çoklu Amazon dosyalarını birleştir ve account bilgisi ekle"""
        combined_df = pd.DataFrame()

        for filename, amazon_df in amazon_files_data:
            # Account ismini extract et
            account_name = self.extract_account_name_from_filename(filename)

            # Her kayda account bilgisi ekle
            amazon_df_copy = amazon_df.copy()
            amazon_df_copy['amazon_account'] = account_name

            # Birleştir
            combined_df = pd.concat([combined_df, amazon_df_copy], ignore_index=True)

            print(f"DEBUG - Added {len(amazon_df)} records from {filename} (account: {account_name})")

        print(f"DEBUG - Combined total: {len(combined_df)} Amazon records from {len(amazon_files_data)} accounts")
        return combined_df

    def combine_ebay_files(self, ebay_files_data: List[Tuple[str, pd.DataFrame]]) -> pd.DataFrame:
        """Çoklu eBay dosyalarını birleştir ve source bilgisi ekle"""
        combined_df = pd.DataFrame()

        for filename, ebay_df in ebay_files_data:
            # Source bilgisi ekle (opsiyonel)
            ebay_df_copy = ebay_df.copy()
            ebay_df_copy['ebay_source'] = filename

            # Birleştir
            combined_df = pd.concat([combined_df, ebay_df_copy], ignore_index=True)

            print(f"DEBUG - Added {len(ebay_df)} eBay records from {filename}")

        print(f"DEBUG - Combined total: {len(combined_df)} eBay records from {len(ebay_files_data)} files")
        return combined_df

    # 🆕 ENHANCED RECORD CREATION WITH INTERNATIONAL INFO
    def create_match_record_with_international(self, ebay_data: Dict, amazon_data: Dict,
                                               match_details: Dict, match_counter: int,
                                               exclude_fields: List[str] = None) -> Dict:
        """Create match record with international routing information"""

        # Use existing create_match_record
        match_record = self.create_match_record(
            ebay_data, amazon_data, match_details, match_counter, exclude_fields
        )

        # Add international-specific fields
        if match_details.get('match_method') == 'eis_co_international':
            international_info = match_details.get('international_info', {})

            # Add international flags
            match_record['is_international_order'] = True
            match_record['routing_method'] = 'eis_co_warehouse'
            match_record['extracted_buyer_name'] = international_info.get('extracted_name', '')
            match_record['name_match_confidence'] = international_info.get('confidence', 0)

            # Add eBay country info
            if 'Ship to country' in ebay_data:
                match_record['ebay_destination_country'] = ebay_data['Ship to country']
        else:
            match_record['is_international_order'] = False
            match_record['routing_method'] = 'direct_shipping'

        return match_record

    def create_match_record(self, ebay_data: Dict, amazon_data: Dict,
                            match_details: Dict, match_counter: int,
                            exclude_fields: List[str] = None) -> Dict:
        """Eşleştirme kaydı oluştur - Amazon account field dahil"""
        if exclude_fields is None:
            exclude_fields = []

        # Master bilgiler
        match_record = {
            'master_no': match_counter
        }

        # eBay alanlarını ekle
        for col, value in ebay_data.items():
            clean_col = str(col).replace(' ', '_').replace('/', '_').lower()
            field_name = f'ebay_{clean_col}'
            if field_name not in exclude_fields:
                match_record[field_name] = value

        # Amazon alanlarını ekle (amazon_account dahil)
        for col, value in amazon_data.items():
            clean_col = str(col).replace(' ', '_').replace('/', '_').lower()
            field_name = f'amazon_{clean_col}'
            if field_name not in exclude_fields:
                match_record[field_name] = value

        # Amazon account field'ını özel olarak handle et
        if 'amazon_account' in amazon_data:
            match_record['amazon_account'] = amazon_data['amazon_account']

        # DEBUG: Amazon products kontrol
        print(f"DEBUG - amazon_data keys: {list(amazon_data.keys())}")
        if 'products' in amazon_data:
            print(f"DEBUG - Found 'products': {amazon_data['products']}")
        if 'amazon_products' in match_record:
            print(f"DEBUG - Found 'amazon_products' in match_record: {match_record['amazon_products']}")

        # AMAZON PRODUCTS - SEPARATE FIELDS PROCESSING
        # YÖNTEİM 1: match_record'dan kontrol
        if 'amazon_products' in match_record and match_record['amazon_products']:
            print("DEBUG - Processing amazon_products from match_record")
            products = match_record['amazon_products']
            if isinstance(products, list) and len(products) > 0:
                product = products[0]
                if isinstance(product, dict):
                    print(f"DEBUG - Product dict: {product}")

                    # Amazon Product Title
                    if 'title' in product and product['title']:
                        match_record['amazon_product_title'] = str(product['title'])
                        print(f"DEBUG - Added amazon_product_title: {product['title']}")

                    # Amazon Product URL
                    if 'url' in product and product['url']:
                        match_record['amazon_product_url'] = str(product['url'])
                        print(f"DEBUG - Added amazon_product_url: {product['url']}")

                        # ASIN extraction
                        url = product['url']
                        import re
                        asin_match = re.search(r'/dp/([A-Z0-9]{10})', url)
                        if not asin_match:
                            asin_match = re.search(r'[?&]asin=([A-Z0-9]{10})', url)

                        if asin_match:
                            match_record['amazon_asin'] = asin_match.group(1)
                            print(f"DEBUG - Added amazon_asin: {asin_match.group(1)}")

            # Remove original array
            del match_record['amazon_products']
            print("DEBUG - Removed original amazon_products array")

        # YÖNTEMİ 2: Raw amazon_data'dan kontrol (fallback)
        elif 'products' in amazon_data and amazon_data['products']:
            print("DEBUG - Processing products from raw amazon_data")
            products = amazon_data['products']
            if isinstance(products, list) and len(products) > 0:
                product = products[0]
                if isinstance(product, dict):
                    print(f"DEBUG - Raw product dict: {product}")

                    if 'title' in product and product['title']:
                        match_record['amazon_product_title'] = str(product['title'])
                        print(f"DEBUG - Added amazon_product_title from raw: {product['title']}")

                    if 'url' in product and product['url']:
                        match_record['amazon_product_url'] = str(product['url'])

                        # ASIN extraction
                        url = product['url']
                        import re
                        asin_match = re.search(r'/dp/([A-Z0-9]{10})', url)
                        if not asin_match:
                            asin_match = re.search(r'[?&]asin=([A-Z0-9]{10})', url)

                        if asin_match:
                            match_record['amazon_asin'] = asin_match.group(1)

        else:
            print("DEBUG - No amazon_products or products found!")

        # Amazon ship_to processing
        if 'amazon_shippingaddress' in match_record:
            shipping_obj = match_record['amazon_shippingaddress']
            if isinstance(shipping_obj, dict):
                ship_to_parts = []

                if 'name' in shipping_obj and shipping_obj['name']:
                    ship_to_parts.append(str(shipping_obj['name']))

                if 'fullAddress' in shipping_obj and shipping_obj['fullAddress']:
                    ship_to_parts.append(str(shipping_obj['fullAddress']))

                if ship_to_parts:
                    match_record['amazon_ship_to'] = '\n'.join(ship_to_parts)

            del match_record['amazon_shippingaddress']

        # Fallback for ship_to
        if 'amazon_ship_to' not in match_record and 'shippingAddress' in amazon_data:
            shipping_obj = amazon_data['shippingAddress']
            if isinstance(shipping_obj, dict):
                ship_to_parts = []

                if 'name' in shipping_obj and shipping_obj['name']:
                    ship_to_parts.append(str(shipping_obj['name']))

                if 'fullAddress' in shipping_obj and shipping_obj['fullAddress']:
                    ship_to_parts.append(str(shipping_obj['fullAddress']))

                if ship_to_parts:
                    match_record['amazon_ship_to'] = '\n'.join(ship_to_parts)

        # Kâr hesaplamalarını ekle
        profit_metrics = calculate_single_order_profit(ebay_data, amazon_data)
        # Kâr hesaplamalarını ekle
        for key, value in profit_metrics.items():
            if key not in exclude_fields:
                match_record[key] = value

        return match_record

    # 🔄 ENHANCED MATCH_ORDERS WITH INTERNATIONAL SUPPORT
    def match_orders(self, ebay_df, amazon_combined_df,
                     ebay_mapping=None, amazon_mapping=None,
                     exclude_fields=None, progress_callback=None) -> pd.DataFrame:
        """Enhanced order matching with international eIS CO support"""

        # UPDATED Default exclude list
        if exclude_fields is None:
            exclude_fields = [
                "match_score", "days_difference", "ebay_transaction_currency",
                "ebay_item_price", "ebay_quantity", "ebay_shipping_and_handling",
                "ebay_ebay_collected_tax", "ebay_item_subtotal", "ebay_seller_collected_tax",
                "ebay_discount", "ebay_payout_currency", "ebay_gross_amount",
                "ebay_final_value_fee_-_fixed", "ebay_final_value_fee_-_variable",
                "ebay_below_standard_performance_fee", "ebay_very_high_\"item_not_as_described\"_fee",
                "ebay_international_fee", "ebay_deposit_processing_fee", "ebay_regulatory_operating_fee",
                "ebay_promoted_listing_standard_fee", "ebay_charity_donation", "ebay_shipping_labels",
                "ebay_payment_dispute_fee", "ebay_expenses", "ebay_order_earnings", "amazon_extractedat",
                "amazon_shippingaddress", "amazon_products", "amazon_ordertotal", "calculated_is_profitable"
            ]

        # Otomatik kolon tespiti
        if ebay_mapping is None:
            ebay_mapping = self.auto_detect_columns(ebay_df, 'ebay')
        if amazon_mapping is None:
            amazon_mapping = self.auto_detect_columns(amazon_combined_df, 'amazon')

        print("🔍 RAW DATA KONTROL:")
        jose_raw = ebay_df[ebay_df['Buyer name'].str.contains('Jose', na=False, case=False)]
        print(f"Raw eBay'de Jose: {len(jose_raw)} records")
        if len(jose_raw) > 0:
            print(f"Jose raw data: '{jose_raw.iloc[0]['Buyer name']}'")

        eis_raw = amazon_combined_df[amazon_combined_df['shippingAddress'].apply(
            lambda x: 'eIS CO' in str(x.get('name', '')) if isinstance(x, dict) else False
        )]
        print(f"Raw Amazon'da eIS CO: {len(eis_raw)} records")

        # Veriyi normalize et
        ebay_normalized = self.normalize_data(ebay_df, ebay_mapping, 'ebay')
        amazon_normalized = self.normalize_data(amazon_combined_df, amazon_mapping, 'amazon')

        print("🔍 NORMALIZED DATA KONTROL:")
        jose_norm = ebay_normalized[ebay_normalized['buyer_name'].str.contains('Jose', na=False, case=False)]
        print(f"Normalized eBay'de Jose: {len(jose_norm)} records")
        if len(jose_norm) > 0:
            print(f"Jose normalized data: '{jose_norm.iloc[0]['buyer_name']}'")
            print(f"Jose index: {jose_norm.index[0]}")
        else:
            print("❌ JOSE NORMALIZATION'DA KAYBOLDU!")

        # Orijinal veri
        ebay_original = ebay_df.copy()
        amazon_original = amazon_combined_df.copy()

        matches = []
        match_counter = 1
        international_matches = 0
        domestic_matches = 0
        used_amazon_orders = set()  # YENİ SATIR - Duplicate control

        print(f"🔍 EŞLEŞTIRME BAŞLIYOR: {len(ebay_normalized)} eBay vs {len(amazon_normalized)} Amazon")

        # Her eBay siparişi için eşleştirme yap
        for ebay_idx, ebay_order in ebay_normalized.iterrows():
            ebay_order_dict = ebay_order.to_dict()

            # JOSE GONZALEZ ÖZEL DEBUG
            if 'jose' in str(ebay_order_dict.get('buyer_name', '')).lower():
                print(f"\n🎯 JOSE GONZALEZ BULUNDU! Index: {ebay_idx}")
                print(f"   eBay Buyer: '{ebay_order_dict.get('buyer_name', 'N/A')}'")
                print(f"   eBay Ürün: '{ebay_order_dict.get('item_title', 'N/A')}'")
                print(f"   eBay Tarih: '{ebay_order_dict.get('order_date', 'N/A')}'")

                potansiyel_sayisi = 0
                eis_co_deneme = 0



                for amazon_idx, amazon_order in amazon_normalized.iterrows():
                    amazon_dict = amazon_order.to_dict()

                    # eIS CO kontrol
                    shipping_addr = amazon_dict.get('shippingAddress', {})
                    if isinstance(shipping_addr, dict):
                        amazon_name = shipping_addr.get('name', '')
                        if 'eIS CO' in str(amazon_name) and 'jose' in str(amazon_name).lower():
                            eis_co_deneme += 1
                            print(f"   🌍 eIS CO José #{eis_co_deneme} ile denendi:")
                            print(f"      Amazon Name: '{amazon_name}'")
                            print(f"      Amazon Ürün: '{amazon_dict.get('item_title', 'N/A')}'")
                            print(f"      Amazon Tarih: '{amazon_dict.get('order_date', 'N/A')}'")

                            # Match score hesapla
                            match_result = self.calculate_match_score_with_international(
                                ebay_order_dict, amazon_dict
                            )

                            print(f"      Match Score: {match_result['total_score']}")
                            print(f"      Is Match: {match_result['is_match']}")
                            print(f"      Match Method: {match_result.get('match_method', 'N/A')}")

                            if match_result['is_match']:
                                potansiyel_sayisi += 1

                print(f"   📊 Jose için eIS CO deneme sayısı: {eis_co_deneme}")
                print(f"   📊 Jose için toplam potansiyel eşleşme: {potansiyel_sayisi}")
                print(f"🎯 JOSE GONZALEZ DEBUG BİTTİ\n")

            if progress_callback:
                progress_callback(ebay_idx + 1, len(ebay_normalized),
                                  ebay_order_dict.get('order_id', 'N/A'))

            # Normal eşleştirme mantığı

                # pages/2_Order_Matcher.py - match_orders fonksiyonunda değişiklik

                # Bu bölümü bulun ve değiştirin (yaklaşık 150-180. satırlar):

                # Normal eşleştirme mantığı
                potential_matches = []

                for amazon_idx, amazon_order in amazon_normalized.iterrows():
                    amazon_dict = amazon_order.to_dict()

                    # Composite key oluştur
                    amazon_composite_key = f"{amazon_dict.get('orderId', '')}_{amazon_dict.get('amazon_account', '')}"

                    # Skip if already used
                    if amazon_composite_key in used_amazon_orders:
                        continue

                    match_result = self.calculate_match_score_with_international(
                        ebay_order_dict, amazon_dict
                    )

                    if match_result['is_match'] and match_result['total_score'] >= self.threshold:
                        potential_matches.append({
                            'amazon_idx': amazon_idx,
                            'amazon_order': amazon_order,
                            'amazon_composite_key': amazon_composite_key,
                            'match_score': match_result['total_score'],
                            'days_difference': match_result.get('days_difference', 0),
                            'match_details': match_result,
                            'amazon_account': amazon_dict.get('amazon_account', 'unknown'),
                            'amazon_orderid': amazon_dict.get('orderId', 'N/A')
                        })

                # En iyi eşleşmeyi seç - DATE-BASED SMART SELECTION
                if not potential_matches:
                    continue

                if len(potential_matches) == 1:
                    best_match = potential_matches[0]
                else:
                    # ENHANCED SELECTION - Date priority
                    print(f"🎯 Multiple matches for eBay {ebay_order_dict.get('buyer_name', 'N/A')}:")

                    # 1. En yakın tarihi bul (minimum days_difference)
                    min_days = min(match['days_difference'] for match in potential_matches)
                    closest_date_matches = [match for match in potential_matches if
                                            match['days_difference'] == min_days]

                    print(f"   📅 Closest date matches ({min_days} days): {len(closest_date_matches)}")

                    if len(closest_date_matches) == 1:
                        best_match = closest_date_matches[0]
                        print(f"   ✅ Selected by date: {best_match['amazon_account']} - {best_match['amazon_orderid']}")
                    else:
                        # 2. Aynı tarihte birden fazla varsa, en yüksek score'u al
                        best_match = max(closest_date_matches, key=lambda x: x['match_score'])
                        print(
                            f"   ✅ Selected by score: {best_match['amazon_account']} - {best_match['amazon_orderid']} (Score: {best_match['match_score']})")

                    # Debug için diğer seçenekleri göster
                    for i, match in enumerate(potential_matches):
                        status = "✅ SELECTED" if match == best_match else "⏭️ Skipped"
                        print(
                            f"   {status} Option {i + 1}: {match['amazon_account']} - Days: {match['days_difference']}, Score: {match['match_score']}")

                # Mark as used BEFORE creating record
                used_amazon_orders.add(best_match['amazon_composite_key'])

                # Record creation (existing code continues...)
                selected_amazon_idx = best_match['amazon_idx']
                # ... rest of the code remains the same
            # Record creation
            selected_amazon_idx = best_match['amazon_idx']
            ebay_original_data = ebay_original.loc[ebay_idx].to_dict()
            amazon_original_data = amazon_original.loc[selected_amazon_idx].to_dict()

            match_record = self.create_match_record_with_international(
                ebay_original_data,
                amazon_original_data,
                best_match['match_details'],
                match_counter,
                exclude_fields=exclude_fields
            )

            matches.append(match_record)
            match_counter += 1

            # Match type tracking
            match_method = best_match['match_details'].get('match_method', 'standard')
            account_name = amazon_original_data.get('amazon_account', 'unknown')

            if match_method == 'eis_co_international':
                international_matches += 1
            else:
                domestic_matches += 1

        # Final statistics
        total_successful_matches = len(matches)
        print(f"\nDEBUG - Matching Summary:")
        print(f"  📊 Total matches found: {total_successful_matches}")
        print(f"  🏠 Domestic matches: {domestic_matches}")
        print(f"  🌍 International (eIS CO) matches: {international_matches}")

        if total_successful_matches > 0:
            international_percentage = (international_matches / total_successful_matches) * 100
            print(f"  📈 International percentage: {international_percentage:.1f}%")

        # FINAL JOSE GONZALEZ DEBUG
        print("\n" + "=" * 50)
        print("🎯 JOSE GONZALEZ FINAL DURUMU:")
        print("=" * 50)

        # Jose Gonzalez eşleşti mi?
        jose_matched = False
        jose_match_info = None

        for match in matches:
            ebay_buyer = match.get('ebay_buyer_name', '')
            if 'jose' in str(ebay_buyer).lower() and 'gonzalez' in str(ebay_buyer).lower():
                jose_matched = True

                amazon_ship_to = match.get('amazon_ship_to', '')
                amazon_orderid = match.get('amazon_orderid', 'N/A')

                if 'eIS CO' in str(amazon_ship_to):
                    jose_match_info = f"🌍 eIS CO ile eşleşti! (Order: {amazon_orderid})"
                else:
                    jose_match_info = f"🏠 Normal sipariş ile eşleşti (Order: {amazon_orderid})"
                break

        if jose_matched:
            print(f"✅ Jose Gonzalez EŞLEŞTİ: {jose_match_info}")
        else:
            print("❌ Jose Gonzalez EŞLEŞMEDİ!")

        print("=" * 50)
        print(f"📊 SONUÇ: {len(matches)} total matches")
        print("=" * 50)

        return pd.DataFrame(matches)


# ========== STREAMLIT UI ==========

def main():
    """Enhanced main function with international eIS CO support"""
    st.markdown("### 📊 Enhanced Multi-Amazon Account Support")

    tab1, tab2, tab3 = st.tabs(["📤 File Upload", "⚙️ Matching Settings", "📊 Results"])

    with tab1:
        st.subheader("📤 Upload JSON Files")

        col1, col2 = st.columns(2)

        with col1:
            st.markdown("#### 🏪 eBay Orders")
            ebay_files = st.file_uploader(
                "Select eBay JSON files",
                type=['json'],
                key="ebay_upload",
                help="Upload multiple eBay JSON files from different stores/periods",
                accept_multiple_files=True
            )

            if ebay_files:
                try:
                    ebay_files_data = []
                    total_ebay_orders = 0

                    st.success(f"✅ {len(ebay_files)} eBay files uploaded")

                    for ebay_file in ebay_files:
                        ebay_data = json.loads(ebay_file.read())

                        # JSON yapısını handle et (aynı logic)
                        if isinstance(ebay_data, list):
                            ebay_df = pd.DataFrame(ebay_data)
                        elif isinstance(ebay_data, dict):
                            possible_keys = ['orders', 'data', 'results', 'items', 'orderDetails']
                            ebay_orders = None

                            for key in possible_keys:
                                if key in ebay_data:
                                    ebay_orders = ebay_data[key]
                                    st.info(f"✅ eBay orders found in '{key}' field")
                                    break

                            ebay_df = pd.DataFrame(ebay_orders if ebay_orders else [ebay_data])
                        else:
                            ebay_df = pd.DataFrame([ebay_data])

                        ebay_files_data.append((ebay_file.name, ebay_df))
                        total_ebay_orders += len(ebay_df)

                        st.info(f"📁 **{ebay_file.name}** → {len(ebay_df)} eBay orders")

                    st.success(f"🎯 **Total: {total_ebay_orders} eBay orders from {len(ebay_files)} files**")
                    st.session_state.ebay_files_data = ebay_files_data

                    # Kolon önizlemesi (ilk dosyadan)
                    if ebay_files_data:
                        first_df = ebay_files_data[0][1]
                        with st.expander("🔍 eBay Columns"):
                            st.write(f"**Total columns:** {len(first_df.columns)}")
                            for col in first_df.columns[:10]:
                                st.write(f"• {col}")
                            if len(first_df.columns) > 10:
                                st.write(f"... and {len(first_df.columns) - 10} more columns")

                except Exception as e:
                    st.error(f"❌ eBay files could not be read: {e}")

        with col2:
            st.markdown("#### 📦 Amazon Orders (Multiple Accounts)")
            amazon_files = st.file_uploader(
                "Select Amazon JSON files",
                type=['json'],
                key="amazon_upload",
                help="Upload multiple Amazon JSON files from different accounts",
                accept_multiple_files=True
            )

            if amazon_files:
                try:
                    amazon_files_data = []
                    total_orders = 0

                    st.success(f"✅ {len(amazon_files)} Amazon files uploaded")

                    for amazon_file in amazon_files:
                        amazon_data = json.loads(amazon_file.read())

                        # JSON yapısını handle et
                        if isinstance(amazon_data, list):
                            amazon_df = pd.DataFrame(amazon_data)
                        elif isinstance(amazon_data, dict):
                            possible_keys = ['orders', 'data', 'results', 'items', 'orderDetails']
                            amazon_orders = None

                            for key in possible_keys:
                                if key in amazon_data:
                                    amazon_orders = amazon_data[key]
                                    break

                            amazon_df = pd.DataFrame(amazon_orders if amazon_orders else [amazon_data])
                        else:
                            amazon_df = pd.DataFrame([amazon_data])

                        amazon_files_data.append((amazon_file.name, amazon_df))
                        total_orders += len(amazon_df)

                        # Format detection ve preview
                        temp_matcher = DropshippingMatcher()
                        detected_format = temp_matcher.detect_amazon_format(amazon_df)
                        account_name = temp_matcher.extract_account_name_from_filename(amazon_file.name)

                        st.info(
                            f"📁 **{amazon_file.name}** → {len(amazon_df)} orders (Account: **{account_name}**, Format: {detected_format.upper()})")

                    st.success(f"🎯 **Total: {total_orders} Amazon orders from {len(amazon_files)} accounts**")
                    st.session_state.amazon_files_data = amazon_files_data

                    # Account summary
                    with st.expander("🔍 Account Summary"):
                        temp_matcher = DropshippingMatcher()
                        for filename, amazon_df in amazon_files_data:
                            account_name = temp_matcher.extract_account_name_from_filename(filename)
                            detected_format = temp_matcher.detect_amazon_format(amazon_df)

                            col_a, col_b, col_c = st.columns(3)
                            with col_a:
                                st.write(f"**Account:** {account_name}")
                            with col_b:
                                st.write(f"**Orders:** {len(amazon_df)}")
                            with col_c:
                                st.write(f"**Format:** {detected_format.upper()}")

                            st.write("---")

                except Exception as e:
                    st.error(f"❌ Amazon files could not be read: {e}")

    with tab2:
        st.subheader("⚙️ Matching Parameters")

        col1, col2 = st.columns(2)

        with col1:
            threshold = st.slider(
                "🎯 Matching Threshold (%)",
                min_value=50,
                max_value=95,
                value=70,
                step=5,
                help="Higher value = stricter matching"
            )

            st.markdown("#### 🔧 Algorithm Weights")
            name_weight = st.slider("👤 Name Weight (%)", 0, 50, 30)
            zip_weight = st.slider("📍 ZIP Code Weight (%)", 0, 50, 25)
            title_weight = st.slider("📦 Product Title (%)", 0, 50, 25)
            city_weight = st.slider("🏙️ City Weight (%)", 0, 30, 12)
            state_weight = st.slider("🗺️ State Weight (%)", 0, 20, 8)

            # Toplam kontrol
            total_weight = name_weight + zip_weight + title_weight + city_weight + state_weight
            if total_weight != 100:
                st.warning(f"⚠️ Total weight: {total_weight}% (should be 100%)")

        with col2:
            st.markdown("#### 📋 Excluded Columns")
            st.write("Columns to exclude from JSON output:")

            exclude_options = [
                "match_score",
                "days_difference",
                "ebay_transaction_currency",
                "ebay_item_price",
                "ebay_quantity",
                "ebay_shipping_and_handling",
                "ebay_ebay_collected_tax",
                "ebay_item_subtotal",
                "ebay_seller_collected_tax",
                "ebay_discount",
                "ebay_payout_currency",
                "ebay_gross_amount",
                "ebay_final_value_fee_-_fixed",
                "ebay_final_value_fee_-_variable",
                "ebay_below_standard_performance_fee",
                "ebay_very_high_\"item_not_as_described\"_fee",
                "ebay_international_fee",
                "ebay_deposit_processing_fee",
                "ebay_regulatory_operating_fee",
                "ebay_promoted_listing_standard_fee",
                "ebay_charity_donation",
                "ebay_shipping_labels",
                "ebay_payment_dispute_fee",
                "ebay_expenses",
                "ebay_order_earnings",
                "amazon_extractedat",
                "amazon_shippingaddress",
                "amazon_products",
                "amazon_ordertotal",
                "cost_calculation_method",
                "calculated_is_profitable"
            ]

            # Varsayılan olarak hepsini seç
            selected_excludes = st.multiselect(
                "Select columns to exclude:",
                options=exclude_options,
                default=exclude_options,
                help="These columns will not appear in the result JSON"
            )

        # 🆕 INTERNATIONAL SETTINGS
        st.markdown("---")
        international_settings = show_international_settings()

    with tab3:
        st.subheader("📊 Matching Results")

        # Eşleştirme başlatma butonu
        if 'ebay_files_data' in st.session_state and 'amazon_files_data' in st.session_state:

            # Pre-matching info
            with st.expander("🔍 Pre-Matching Information"):
                st.write("### Multi-Account Amazon Processing")

                amazon_files_data = st.session_state.amazon_files_data
                temp_matcher = DropshippingMatcher()

                # Account breakdown
                for filename, amazon_df in amazon_files_data:
                    account_name = temp_matcher.extract_account_name_from_filename(filename)
                    amazon_format = temp_matcher.detect_amazon_format(amazon_df)

                    col1, col2, col3, col4 = st.columns(4)
                    col1.metric("Account", account_name)
                    col2.metric("Orders", len(amazon_df))
                    col3.metric("Format", amazon_format.upper())

                    try:
                        sample_df = amazon_df.head(1).copy()
                        normalized_sample = temp_matcher.normalize_amazon_data_enhanced(sample_df)
                        has_address = (normalized_sample['full_address'].notna() &
                                       (normalized_sample['full_address'] != '')).sum()
                        address_quality = "✅ Good" if has_address > 0 else "⚠️ Poor"
                        col4.metric("Address Quality", address_quality)
                    except:
                        col4.metric("Address Quality", "❌ Error")

                    st.write("---")

            col1, col2, col3 = st.columns([1, 2, 1])

            with col2:
                if st.button("🚀 Start Enhanced Multi-Account Matching", type="primary", use_container_width=True):

                    with st.spinner("🔄 Enhanced multi-account order matching in progress..."):
                        try:
                            # Matcher'ı oluştur
                            matcher = DropshippingMatcher(threshold=threshold)

                            # 🆕 INTERNATIONAL SETTINGS APPLY
                            if international_settings['enable_international']:
                                matcher.international_matcher.update_thresholds(
                                    name_threshold=international_settings['name_threshold'],
                                    product_threshold=international_settings['product_threshold']
                                )
                                st.info(
                                    f"🌍 International matching enabled - Name: {international_settings['name_threshold']}%, Product: {international_settings['product_threshold']}%")

                            # Ağırlıkları güncelle
                            if total_weight == 100:
                                matcher.weights = {
                                    'name': name_weight / 100,
                                    'zip': zip_weight / 100,
                                    'title': title_weight / 100,
                                    'city': city_weight / 100,
                                    'state': state_weight / 100
                                }
                            else:
                                st.warning("⚠️ Weight total is not 100%, using default weights")

                            # Progress tracking
                            progress_bar = st.progress(0)
                            status_text = st.empty()

                            def update_progress(current, total, order_id):
                                if total > 0:
                                    progress = current / total
                                    progress_bar.progress(progress)
                                status_text.text(f"🔍 Processing: {current}/{total} - {order_id}")

                            # Amazon dosyalarını birleştir
                            status_text.text("🔄 Combining Amazon accounts...")
                            amazon_files_data = st.session_state.amazon_files_data
                            amazon_combined_df = matcher.combine_amazon_files(amazon_files_data)

                            # eBay dosyalarını birleştir
                            status_text.text("🔄 Combining eBay files...")
                            ebay_files_data = st.session_state.ebay_files_data
                            ebay_combined_df = matcher.combine_ebay_files(ebay_files_data)

                            status_text.text(
                                f"✅ Combined {len(ebay_combined_df)} eBay orders from {len(ebay_files_data)} files and {len(amazon_combined_df)} Amazon orders from {len(amazon_files_data)} accounts")

                            status_text.text("🔍 Starting enhanced multi-account order matching...")

                            # 🆕 ENHANCED MATCHING
                            results = matcher.match_orders(
                                ebay_df=ebay_combined_df,
                                amazon_combined_df=amazon_combined_df,
                                ebay_mapping=None,
                                amazon_mapping=None,
                                exclude_fields=selected_excludes,
                                progress_callback=update_progress
                            )

                            # Progress tamamlandı
                            progress_bar.progress(1.0)
                            status_text.text("✅ Enhanced multi-account matching completed!")

                            # Sonuçları session'a kaydet
                            st.session_state.match_results = results

                            if len(results) > 0:
                                st.success(f"🎉 Enhanced matching completed! {len(results)} matches found")

                                # 🆕 INTERNATIONAL STATISTICS
                                if 'is_international_order' in results.columns:
                                    international_count = results['is_international_order'].sum()
                                    domestic_count = len(results) - international_count

                                    st.info(
                                        f"📊 **Match Breakdown:** {domestic_count} domestic, {international_count} international (eIS CO)")

                                    if international_count > 0:
                                        st.success(
                                            f"🌍 **eIS CO Detection:** Successfully matched {international_count} international orders!")

                                # Account bazında breakdown
                                if 'amazon_account' in results.columns:
                                    account_breakdown = results['amazon_account'].value_counts()
                                    st.info("📊 **Matches by Account:**")
                                    for account, count in account_breakdown.items():
                                        st.write(f"• **{account}:** {count} matches")

                                # Kâr özeti
                                if 'calculated_profit_usd' in results.columns:
                                    total_profit = results['calculated_profit_usd'].sum()
                                    profitable_count = (results['calculated_profit_usd'] > 0).sum()

                                    st.info(
                                        f"💰 Total Profit: ${total_profit:,.2f} | ✅ Profitable Orders: {profitable_count}")

                            else:
                                st.warning("⚠️ No matches found. Try lowering the threshold value.")

                        except Exception as e:
                            st.error(f"❌ Matching error: {e}")
                            import traceback
                            with st.expander("🔍 Error Details"):
                                st.code(traceback.format_exc())

        else:
            st.info("📤 Please upload eBay JSON file and multiple Amazon JSON files first")

        # 🆕 ENHANCED RESULTS DISPLAY
        if 'match_results' in st.session_state:
            results = st.session_state.match_results

            if not results.empty:
                # Enhanced özet metrikler
                st.markdown("#### 📈 Enhanced Summary Metrics")

                col1, col2, col3, col4 = st.columns(4)

                with col1:
                    total_matches = len(results)
                    st.metric("🔗 Total Matches", total_matches)

                with col2:
                    if 'calculated_profit_usd' in results.columns:
                        total_profit = results['calculated_profit_usd'].sum()
                        st.metric("💰 Total Profit", f"${total_profit:,.2f}")
                    else:
                        st.metric("💰 Total Profit", "N/A")

                with col3:
                    # 🆕 INTERNATIONAL METRIC
                    if 'is_international_order' in results.columns:
                        international_count = results['is_international_order'].sum()
                        st.metric("🌍 International Orders", international_count)
                    else:
                        st.metric("🌍 International Orders", "N/A")

                with col4:
                    if 'calculated_profit_usd' in results.columns:
                        profitable_count = (results['calculated_profit_usd'] > 0).sum()
                        st.metric("✅ Profitable Orders", profitable_count)
                    else:
                        st.metric("✅ Profitable Orders", "N/A")

                # Account performance breakdown
                if 'amazon_account' in results.columns:
                    st.markdown("#### 📊 Account Performance")

                    account_metrics = results.groupby('amazon_account').agg({
                        'calculated_profit_usd': ['count', 'sum', 'mean'],
                        'calculated_amazon_cost_usd': 'sum',
                        'calculated_ebay_earning_usd': 'sum'
                    }).round(2)

                    account_metrics.columns = ['Orders', 'Total Profit', 'Avg Profit', 'Total Cost', 'Total Revenue']
                    account_metrics['ROI %'] = (
                            (account_metrics['Total Profit'] / account_metrics['Total Cost']) * 100).round(1)

                    st.dataframe(account_metrics, use_container_width=True)

                # Enhanced data table with international info
                st.markdown("#### 📋 Match Details")

                # Display columns selection
                display_columns = []
                if 'master_no' in results.columns:
                    display_columns.append('master_no')

                # Amazon account
                if 'amazon_account' in results.columns:
                    display_columns.append('amazon_account')

                # International info
                if 'is_international_order' in results.columns:
                    display_columns.append('is_international_order')
                if 'routing_method' in results.columns:
                    display_columns.append('routing_method')

                # Important columns
                important_cols = ['ebay_order_number', 'amazon_orderid', 'calculated_profit_usd']
                for col in important_cols:
                    if col in results.columns:
                        display_columns.append(col)

                if display_columns:
                    st.dataframe(results[display_columns], use_container_width=True)

                # 🆕 ENHANCED DOWNLOAD OPTIONS
                st.markdown("#### 💾 Enhanced Download Options")

                col1, col2 = st.columns(2)

                with col1:
                    # JSON indirme
                    json_data = results.to_json(orient='records', indent=2)
                    if st.download_button(
                            label="📄 Download Enhanced JSON",
                            data=json_data,
                            file_name=f"enhanced_matched_orders_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                            mime="application/json"
                    ):
                        st.success("✅ Enhanced JSON file downloaded!")

                with col2:
                    # CSV indirme
                    csv_data = results.to_csv(index=False)
                    if st.download_button(
                            label="📊 Download Enhanced CSV",
                            data=csv_data,
                            file_name=f"enhanced_matched_orders_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                            mime="text/csv"
                    ):
                        st.success("✅ Enhanced CSV file downloaded!")

            else:
                st.warning("⚠️ No matches found")

    # Enhanced help section
    st.markdown("---")
    with st.expander("❓ Enhanced Multi-Amazon Account & International eIS CO Support Help"):
        st.markdown("""
        **🚀 Enhanced Features:**

        **🌍 International eIS CO Support:**
        - Automatically detects international orders routed through eIS CO warehouse
        - Matches "eIS CO [Customer Name]" pattern with eBay buyer names
        - Separate thresholds for international vs domestic orders
        - Enhanced statistics showing domestic vs international breakdown

        **✅ File Naming Convention:**
        - **buyer1_amazon.json** → Account: "buyer1"
        - **seller3_orders.json** → Account: "seller3"  

        **🔧 Enhanced Processing:**
        - International pattern detection with high confidence matching
        - eIS CO warehouse routing recognition
        - Country-based order classification
        - Detailed match method tracking

        **📊 Enhanced Results:**
        - International vs domestic match statistics
        - eIS CO confidence levels
        - Routing method indicators
        - Account performance analysis
        """)

    # 🔍 MISSING ORDERS ANALYSIS - DOWNLOAD BUTTONS'DAN ÖNCE EKLE
    if 'match_results' in st.session_state:
        results = st.session_state.match_results

        if hasattr(results, 'empty') and not results.empty:
            st.markdown("---")
            st.markdown("### 🔍 Account-Separated Debug Analysis")

            # Quick stats
            col1, col2, col3 = st.columns(3)

            if 'ebay_files_data' in st.session_state and 'amazon_files_data' in st.session_state:
                try:
                    # Get account-separated debug statistics
                    debug_analyzer = AccountSeparatedDebugAnalyzer()

                    # Recreate original data
                    temp_matcher = DropshippingMatcher()
                    amazon_combined_df = temp_matcher.combine_amazon_files(st.session_state.amazon_files_data)
                    ebay_combined_df = temp_matcher.combine_ebay_files(st.session_state.ebay_files_data)

                    debug_stats = debug_analyzer.get_account_debug_statistics(
                        amazon_combined_df, results
                    )

                    with col1:
                        if debug_stats:
                            st.metric("Total Accounts", debug_stats['total_accounts'])
                        else:
                            st.metric("Total Accounts", "N/A")

                    with col2:
                        if debug_stats:
                            st.metric("Accounts with Issues", debug_stats['problematic_accounts'])
                        else:
                            st.metric("Accounts with Issues", "N/A")

                    with col3:
                        if debug_stats:
                            total_missing = debug_stats['overall_missing']
                            st.metric("Total Missing Orders", total_missing,
                                      delta=f"-{total_missing}" if total_missing > 0 else None)
                        else:
                            st.metric("Total Missing Orders", "N/A")

                    # Detailed analysis in expander
                    if debug_stats and (debug_stats['overall_missing'] > 0 or debug_stats['problematic_accounts'] > 0):
                        with st.expander(f"🔍 Analyze {debug_stats['total_accounts']} Accounts Independently"):
                            debug_analyzer.show_isolated_account_analysis(
                                original_amazon_files_data=st.session_state.amazon_files_data,
                                original_ebay_files_data=st.session_state.ebay_files_data,
                                matched_results=results
                            )
                    elif debug_stats:
                        st.success("✅ All accounts matched successfully!")

                except Exception as e:
                    with col1:
                        st.error("Account debug analysis failed")

                    if st.button("Show error details"):
                        st.exception(e)


    # Footer
    st.caption("🔗 Order Matcher | Enhanced with Multi-Amazon Account & International eIS CO Support")


# 🆕 INTERNATIONAL SETTINGS FUNCTION
def show_international_settings():
    """International matching settings UI component"""
    st.markdown("#### 🌍 International Matching Settings")

    col1, col2 = st.columns(2)

    with col1:
        enable_international = st.checkbox(
            "Enable eIS CO International Matching",
            value=True,
            help="Detect and match international orders routed through eIS CO warehouse"
        )

        name_threshold = st.slider(
            "Name Similarity Threshold (%)",
            min_value=70,
            max_value=95,
            value=85,  # GÜNCELLENEN: 90 → 85
            step=5,
            help="Minimum similarity for eIS CO name extraction"
        )

    with col2:
        product_threshold = st.slider(
            "Product Similarity Threshold (%) - International",
            min_value=40,  # GÜNCELLENEN: 50 → 40 (daha esnek range)
            max_value=70,  # GÜNCELLENEN: 80 → 70
            value=50,      # AYNI KALDI
            step=5,
            help="Lower threshold for international orders"
        )

        show_debug = st.checkbox(
            "Enable eIS CO Debug Output",
            value=False,  # GÜNCELLENEN: True → False (default off)
            help="Show detailed eIS CO pattern detection in console"
        )

    return {
        'enable_international': enable_international,
        'name_threshold': name_threshold,
        'product_threshold': product_threshold,
        'show_debug': show_debug
    }

if __name__ == "__main__":
    main()
else:
    # Streamlit import edildiğinde otomatik çalıştır
    main()