import streamlit as st
import pandas as pd
import json
import re
from datetime import datetime
from typing import Dict, List, Tuple, Optional
import warnings

# Import gerekli kütüphaneler
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

    # ========== UTILITY FUNCTIONS ==========

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

    def parse_usd_amount(self, amount_string: str) -> float:
        """USD/TRY string'ini float'a çevir"""
        if not amount_string or pd.isna(amount_string):
            return 0.0

        amount_str = str(amount_string).strip()

        # USD için: "$25.50", "USD 25.50", "25.50 USD"
        if 'USD' in amount_str or '$' in amount_str:
            clean_str = amount_str.replace('USD', '').replace('$', '').strip()
        else:
            # TRY için: "TRY 693.08", "693.08 TRY", "₺693.08"
            clean_str = amount_str.replace('TRY', '').replace('₺', '').strip()

        # Virgülleri handle et
        if ',' in clean_str and '.' in clean_str:
            clean_str = clean_str.replace(',', '')
        elif ',' in clean_str and '.' not in clean_str:
            clean_str = clean_str.replace(',', '.')

        # Sayıları extract et
        numbers = re.findall(r'\d+\.?\d*', clean_str)
        if numbers:
            try:
                return float(numbers[-1])
            except ValueError:
                return 0.0

        return 0.0

    # ========== NEW ADDRESS EXTRACTION FUNCTIONS ==========

    def detect_amazon_format(self, amazon_df: pd.DataFrame) -> str:
        """Amazon format'ını tespit et"""
        new_format_columns = ['orderTotal', 'orderDate', 'shippingAddress']
        if any(col in amazon_df.columns for col in new_format_columns):
            return "new"
        old_format_columns = ['grand_total', 'order_date', 'ship_to']
        if any(col in amazon_df.columns for col in old_format_columns):
            return "old"
        return "unknown"

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
        name_score = self.find_best_match_in_address(
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

    def calculate_match_score(self, ebay_order: Dict, amazon_order: Dict) -> Dict:
        """Override mevcut calculate_match_score fonksiyonu"""
        return self.calculate_match_score_enhanced(ebay_order, amazon_order)

    # TRY → USD çevirim - Embedded rate olmadan (4 yöntem)

    def calculate_profit_metrics(self, ebay_data: Dict, amazon_data: Dict) -> Dict:
        """Kâr metriklerini hesapla - ROI dahil + Gerçek kur bilgisi"""
        try:
            # Exchange rate handler'ı import et (opsiyonel)
            try:
                import sys, os
                sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
                from utils.exchange_rate_handler import ExchangeRateHandler
                rate_handler = ExchangeRateHandler()
            except ImportError:
                rate_handler = None

            # eBay geliri
            ebay_earning = 0.0
            for field in ['Order earnings', 'order_earnings', 'earnings', 'profit', 'revenue']:
                if field in ebay_data and pd.notna(ebay_data[field]):
                    try:
                        ebay_earning = float(ebay_data[field])
                        break
                    except (ValueError, TypeError):
                        continue

            # Amazon maliyeti hesaplama - 4 YÖNTEMLİ + KUR BİLGİSİ
            amazon_cost_usd = 0.0
            cost_calculation_method = "unknown"
            actual_exchange_rate = None

            order_total = amazon_data.get('orderTotal') or amazon_data.get('grand_total', '')

            # PRIORITY 1: USD Direct
            if order_total and 'USD' in str(order_total):
                usd_amount = self.parse_usd_amount(str(order_total))
                if usd_amount > 0:
                    amazon_cost_usd = usd_amount
                    cost_calculation_method = "usd_direct_no_conversion"

            # PRIORITY 2: TRY + API (KUR BİLGİSİ ALMA)
            elif order_total and 'TRY' in str(order_total) and rate_handler:
                order_date = amazon_data.get('orderDate') or amazon_data.get('order_date', '')

                if order_date:
                    success, calculated_cost, calc_message = rate_handler.calculate_amazon_cost_usd(
                        order_total, order_date
                    )

                    if success:
                        amazon_cost_usd = calculated_cost

                        # GERÇEK KUR BİLGİSİNİ AL
                        try_amount = self.parse_usd_amount(order_total)  # TRY miktarı
                        if try_amount > 0 and calculated_cost > 0:
                            actual_exchange_rate = round(try_amount / calculated_cost, 2)
                            cost_calculation_method = f"api_rate_{actual_exchange_rate}_try_per_usd"
                        else:
                            cost_calculation_method = "api_conversion_success"

            # PRIORITY 3: Existing USD Field
            if amazon_cost_usd == 0.0:  # Yukarıdakiler başarısızsa
                for field in ['amazon_cost_usd', 'Amazon cost USD', 'cost_usd', 'usd_cost']:
                    if field in amazon_data and pd.notna(amazon_data[field]):
                        amazon_cost_str = str(amazon_data[field])
                        if amazon_cost_str and amazon_cost_str != 'Not available':
                            parsed_usd = self.parse_usd_amount(amazon_cost_str)
                            if parsed_usd > 0:
                                amazon_cost_usd = parsed_usd
                                cost_calculation_method = "existing_usd_field"
                                break

            # PRIORITY 4: Sabit Kur Fallback (KUR BİLGİSİ)
            if amazon_cost_usd == 0.0 and order_total and 'TRY' in str(order_total):
                try_amount = self.parse_usd_amount(order_total)  # TRY parse eder
                if try_amount > 0:
                    # Sabit kur kullan (güncel TRY/USD ~34)
                    FALLBACK_RATE = 34.0  # 1 USD = 34 TRY
                    amazon_cost_usd = try_amount / FALLBACK_RATE
                    actual_exchange_rate = FALLBACK_RATE
                    cost_calculation_method = f"fallback_rate_{FALLBACK_RATE}_try_per_usd"

            # Hesaplamalar
            profit_usd = ebay_earning - amazon_cost_usd
            margin_percent = (profit_usd / ebay_earning * 100) if ebay_earning > 0 else 0

            # ROI hesaplaması: (Profit / Investment) * 100
            # Investment = Amazon cost (ne kadar para harcadık)
            roi_percent = (profit_usd / amazon_cost_usd * 100) if amazon_cost_usd > 0 else 0

            return {
                'calculated_ebay_earning_usd': round(ebay_earning, 2),
                'calculated_amazon_cost_usd': round(amazon_cost_usd, 2),
                'calculated_profit_usd': round(profit_usd, 2),
                'calculated_margin_percent': round(margin_percent, 2),
                'calculated_roi_percent': round(roi_percent, 2),
                'cost_calculation_method': cost_calculation_method,  # Artık kur bilgisi içeriyor
                'exchange_rate_used': actual_exchange_rate  # YENİ EKLENEN - Kullanılan kur
            }

        except Exception as e:
            return {
                'calculated_ebay_earning_usd': 0.0,
                'calculated_amazon_cost_usd': 0.0,
                'calculated_profit_usd': 0.0,
                'calculated_margin_percent': 0.0,
                'calculated_roi_percent': 0.0,
                'cost_calculation_method': f"error: {str(e)}",
                'exchange_rate_used': None
            }

    def create_match_record(self, ebay_data: Dict, amazon_data: Dict,
                            match_details: Dict, match_counter: int,
                            exclude_fields: List[str] = None) -> Dict:
        """Eşleştirme kaydı oluştur"""
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

        # Amazon alanlarını ekle
        for col, value in amazon_data.items():
            clean_col = str(col).replace(' ', '_').replace('/', '_').lower()
            field_name = f'amazon_{clean_col}'
            if field_name not in exclude_fields:
                match_record[field_name] = value

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
        profit_metrics = self.calculate_profit_metrics(ebay_data, amazon_data)
        for key, value in profit_metrics.items():
            if key not in exclude_fields:
                match_record[key] = value

        return match_record

    # UPDATED exclude_fields list - amazon_shippingaddress'i exclude et
    def match_orders(self, ebay_df: pd.DataFrame, amazon_df: pd.DataFrame,
                     ebay_mapping: Dict[str, str] = None,
                     amazon_mapping: Dict[str, str] = None,
                     exclude_fields: List[str] = None,
                     progress_callback=None) -> pd.DataFrame:
        """Ana eşleştirme fonksiyonu"""

        # UPDATED Default exclude list
        if exclude_fields is None:
            exclude_fields = [
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
                "ebay_order_earnings",  # YENİ EKLENEN
                "amazon_extractedat",
                "amazon_shippingaddress",
                "amazon_products",
                "amazon_ordertotal",  # YENİ EKLENEN
                "calculated_is_profitable"
            ]

        # Otomatik kolon tespiti
        if ebay_mapping is None:
            ebay_mapping = self.auto_detect_columns(ebay_df, 'ebay')
        if amazon_mapping is None:
            amazon_mapping = self.auto_detect_columns(amazon_df, 'amazon')

        # Veriyi normalize et
        ebay_normalized = self.normalize_data(ebay_df, ebay_mapping, 'ebay')
        amazon_normalized = self.normalize_data(amazon_df, amazon_mapping, 'amazon')

        # Orijinal veri
        ebay_original = ebay_df.copy()
        amazon_original = amazon_df.copy()

        matches = []
        match_counter = 1

        # Her eBay siparişi için eşleştirme yap
        for ebay_idx, ebay_order in ebay_normalized.iterrows():
            ebay_order_dict = ebay_order.to_dict()

            if progress_callback:
                progress_callback(ebay_idx + 1, len(ebay_normalized),
                                  ebay_order_dict.get('order_id', 'N/A'))

            # Potansiyel eşleşmeleri bul
            potential_matches = []

            for amazon_idx, amazon_order in amazon_normalized.iterrows():
                match_result = self.calculate_match_score(ebay_order_dict, amazon_order.to_dict())

                if match_result['is_match'] and match_result['total_score'] >= self.threshold:
                    potential_matches.append({
                        'amazon_idx': amazon_idx,
                        'amazon_order': amazon_order,
                        'match_score': match_result['total_score'],
                        'days_difference': match_result['days_difference']
                    })

            # En iyi eşleşmeyi seç
            if not potential_matches:
                continue

            if len(potential_matches) == 1:
                best_match = potential_matches[0]
            else:
                # Birden fazla eşleşme - en yakın tarihi seç
                min_days = min(match['days_difference'] for match in potential_matches)
                closest_matches = [match for match in potential_matches if match['days_difference'] == min_days]

                if len(closest_matches) == 1:
                    best_match = closest_matches[0]
                else:
                    # Aynı tarih farkı - en yüksek skoru seç
                    best_match = max(closest_matches, key=lambda x: x['match_score'])

            # Eşleştirme kaydı oluştur
            selected_amazon_idx = best_match['amazon_idx']
            ebay_original_data = ebay_original.loc[ebay_idx].to_dict()
            amazon_original_data = amazon_original.loc[selected_amazon_idx].to_dict()

            match_record = self.create_match_record(
                ebay_original_data,
                amazon_original_data,
                best_match,
                match_counter,
                exclude_fields=exclude_fields
            )

            matches.append(match_record)
            match_counter += 1

        return pd.DataFrame(matches)


# ========== STREAMLIT UI ==========

def main():
    st.markdown("### 📊 Enhanced Amazon Format Support")

    tab1, tab2, tab3 = st.tabs(["📤 File Upload", "⚙️ Matching Settings", "📊 Results"])

    with tab1:
        st.subheader("📤 Upload JSON Files")

        col1, col2 = st.columns(2)

        with col1:
            st.markdown("#### 🏪 eBay Orders")
            ebay_file = st.file_uploader(
                "Select eBay JSON file",
                type=['json'],
                key="ebay_upload",
                help="Upload your order data exported from eBay"
            )

            if ebay_file:
                try:
                    ebay_data = json.loads(ebay_file.read())

                    # JSON yapısını handle et
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

                    st.success(f"✅ {len(ebay_df)} eBay orders loaded")
                    st.session_state.ebay_df = ebay_df

                    # Kolon önizlemesi
                    with st.expander("🔍 eBay Columns"):
                        st.write(f"**Total columns:** {len(ebay_df.columns)}")
                        for col in ebay_df.columns[:10]:
                            st.write(f"• {col}")
                        if len(ebay_df.columns) > 10:
                            st.write(f"... and {len(ebay_df.columns) - 10} more columns")

                except Exception as e:
                    st.error(f"❌ eBay file could not be read: {e}")

        with col2:
            st.markdown("#### 📦 Amazon Orders")
            amazon_file = st.file_uploader(
                "Select Amazon JSON file",
                type=['json'],
                key="amazon_upload",
                help="Upload your order data exported from Amazon (supports all formats)"
            )

            if amazon_file:
                try:
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
                                st.info(f"✅ Amazon orders found in '{key}' field")
                                break

                        amazon_df = pd.DataFrame(amazon_orders if amazon_orders else [amazon_data])
                    else:
                        amazon_df = pd.DataFrame([amazon_data])

                    # Format detection ve preview
                    temp_matcher = DropshippingMatcher()
                    detected_format = temp_matcher.detect_amazon_format(amazon_df)

                    if detected_format == "new":
                        st.success(f"✅ {len(amazon_df)} Amazon orders loaded (NEW FORMAT)")
                        st.info("🔄 Auto-converting new format to compatible structure...")

                        # Address preview için sample göster
                        if len(amazon_df) > 0:
                            sample_row = amazon_df.iloc[0]

                            with st.expander("🔍 Address Extraction Preview"):
                                st.write("**Sample Row Address Processing:**")

                                if 'shippingAddress' in sample_row and pd.notna(sample_row['shippingAddress']):
                                    shipping_obj = sample_row['shippingAddress']

                                    # Test address extraction
                                    address_parts = temp_matcher.extract_address_from_shipping_object(shipping_obj)
                                    full_address = temp_matcher.build_full_address_string(address_parts)

                                    col_a, col_b = st.columns(2)

                                    with col_a:
                                        st.write("**Raw shippingAddress:**")
                                        if isinstance(shipping_obj, str):
                                            try:
                                                shipping_display = json.loads(shipping_obj)
                                                st.json(shipping_display)
                                            except:
                                                st.code(shipping_obj)
                                        else:
                                            st.json(shipping_obj)

                                    with col_b:
                                        st.write("**Extracted full_address:**")
                                        st.code(full_address)

                                        st.write("**Address parts:**")
                                        for key, value in address_parts.items():
                                            st.write(f"• {key}: {value}")

                    elif detected_format == "old":
                        st.success(f"✅ {len(amazon_df)} Amazon orders loaded (OLD FORMAT)")
                        st.info("📋 Old format uses direct ship_to field")
                    else:
                        st.warning(f"⚠️ {len(amazon_df)} Amazon orders loaded (UNKNOWN FORMAT)")
                        st.error("🔍 Manual column mapping may be required")

                    st.session_state.amazon_df = amazon_df

                    # Kolon önizlemesi
                    with st.expander("🔍 Amazon Columns"):
                        st.write(f"**Total columns:** {len(amazon_df.columns)}")
                        st.write(f"**Detected format:** {detected_format.upper()}")
                        for col in amazon_df.columns[:10]:
                            st.write(f"• {col}")
                        if len(amazon_df.columns) > 10:
                            st.write(f"... and {len(amazon_df.columns) - 10} more columns")

                except Exception as e:
                    st.error(f"❌ Amazon file could not be read: {e}")

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

        # CORRECTED exclude_options - Amazon product fields KORUNUYOR
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
            "amazon_products",  # Array exclude edilir, separate fields korunur
            "amazon_ordertotal",
            "cost_calculation_method",
            "calculated_is_profitable"
            # NOT: amazon_product_title, amazon_product_url, amazon_asin BU LİSTEDE YOK!
        ]

        # Varsayılan olarak hepsini seç
        selected_excludes = st.multiselect(
            "Select columns to exclude:",
            options=exclude_options,
            default=exclude_options,  # Hepsini varsayılan olarak exclude et
            help="These columns will not appear in the result JSON"
        )

    with tab3:
        st.subheader("📊 Matching Results")

        # Eşleştirme başlatma butonu
        if 'ebay_df' in st.session_state and 'amazon_df' in st.session_state:

            # Address Quality Check bölümü
            with st.expander("🔍 Pre-Matching Address Quality Check"):
                st.write("### Amazon Address Quality Analysis")

                amazon_df = st.session_state.amazon_df
                temp_matcher = DropshippingMatcher()

                # Amazon formatını detect et
                amazon_format = temp_matcher.detect_amazon_format(amazon_df)
                st.info(f"📊 **Detected Format:** {amazon_format.upper()}")

                # Sample normalize et
                sample_size = min(5, len(amazon_df))
                sample_df = amazon_df.head(sample_size).copy()
                normalized_sample = temp_matcher.normalize_amazon_data_enhanced(sample_df)

                # Address quality metrics
                total_rows = len(normalized_sample)
                has_full_address = (normalized_sample['full_address'].notna() &
                                    (normalized_sample['full_address'] != '')).sum()

                col1, col2, col3 = st.columns(3)
                col1.metric("Total Sample Rows", total_rows)
                col2.metric("Has Full Address", has_full_address)
                col3.metric("Address Success Rate", f"{(has_full_address / total_rows * 100):.1f}%")

                # Sample address'leri göster
                if has_full_address > 0:
                    st.write("**Sample Extracted Addresses:**")
                    for idx, row in normalized_sample.iterrows():
                        if pd.notna(row['full_address']) and row['full_address']:
                            st.write(f"**Row {idx}:**")
                            address_lines = str(row['full_address']).split('\n')
                            for line in address_lines:
                                st.write(f"  {line}")
                            st.write("---")
                            break

            col1, col2, col3 = st.columns([1, 2, 1])

            with col2:
                if st.button("🚀 Start Matching", type="primary", use_container_width=True):

                    with st.spinner("🔄 Order matching in progress..."):
                        try:
                            # Matcher'ı oluştur
                            matcher = DropshippingMatcher(threshold=threshold)

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

                            # Format detection
                            amazon_format = matcher.detect_amazon_format(st.session_state.amazon_df)
                            status_text.text(f"📊 Detected Amazon format: {amazon_format.upper()}")

                            # Address normalization test
                            status_text.text("🔄 Testing address normalization...")
                            test_amazon_sample = st.session_state.amazon_df.head(1).copy()
                            test_normalized = matcher.normalize_amazon_data_enhanced(test_amazon_sample)

                            if len(test_normalized) > 0 and pd.notna(test_normalized.iloc[0]['full_address']):
                                status_text.text("✅ Address normalization successful")
                            else:
                                st.warning("⚠️ Address normalization may have issues")

                            status_text.text("🔍 Starting order matching algorithm...")

                            # Eşleştirme yap
                            results = matcher.match_orders(
                                ebay_df=st.session_state.ebay_df,
                                amazon_df=st.session_state.amazon_df,
                                ebay_mapping=None,  # Auto-detect
                                amazon_mapping=None,  # Auto-detect
                                exclude_fields=selected_excludes,
                                progress_callback=update_progress
                            )

                            # Progress tamamlandı
                            progress_bar.progress(1.0)
                            status_text.text("✅ Matching completed!")

                            # Sonuçları session'a kaydet
                            st.session_state.match_results = results

                            if len(results) > 0:
                                st.success(f"🎉 Matching completed! {len(results)} matches found")

                                # Kâr özeti
                                if 'calculated_profit_usd' in results.columns:
                                    total_profit = results['calculated_profit_usd'].sum()
                                    profitable_count = (results['calculated_profit_usd'] > 0).sum()
                                    zero_cost_count = (results['calculated_amazon_cost_usd'] == 0).sum()

                                    st.info(
                                        f"💰 Total Profit: ${total_profit:,.2f} | ✅ Profitable Orders: {profitable_count}")

                                    # Cost calculation warnings
                                    if zero_cost_count > 0:
                                        st.warning(
                                            f"⚠️ {zero_cost_count} orders have $0 Amazon cost (calculation failed)")

                            else:
                                st.warning("⚠️ No matches found. Try lowering the threshold value.")

                        except Exception as e:
                            st.error(f"❌ Matching error: {e}")
                            import traceback
                            with st.expander("🔍 Error Details"):
                                st.code(traceback.format_exc())

        else:
            st.info("📤 Please upload both JSON files first")

        # Sonuçları göster
        if 'match_results' in st.session_state:
            results = st.session_state.match_results

            if not results.empty:
                # Özet metrikler
                st.markdown("#### 📈 Summary Metrics")

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
                    if 'calculated_profit_usd' in results.columns:
                        profitable_count = (results['calculated_profit_usd'] > 0).sum()
                        st.metric("✅ Profitable Orders", profitable_count)
                    else:
                        st.metric("✅ Profitable Orders", "N/A")

                with col4:
                    if 'calculated_profit_usd' in results.columns:
                        avg_profit = results['calculated_profit_usd'].mean()
                        st.metric("📊 Average Profit", f"${avg_profit:.2f}")
                    else:
                        st.metric("📊 Average Profit", "N/A")

                # Kâr dağılımı grafiği
                if 'calculated_profit_usd' in results.columns and PLOTLY_AVAILABLE:
                    st.markdown("#### 📊 Profit Distribution")

                    try:
                        fig = px.histogram(
                            results,
                            x='calculated_profit_usd',
                            title="Order Profit Distribution",
                            nbins=30,
                            labels={'calculated_profit_usd': 'Profit ($)', 'count': 'Number of Orders'}
                        )
                        fig.update_layout(
                            xaxis_title="Profit ($)",
                            yaxis_title="Number of Orders"
                        )
                        st.plotly_chart(fig, use_container_width=True)
                    except Exception as e:
                        st.warning(f"⚠️ Chart could not be created: {e}")

                # Detay tablosu
                st.markdown("#### 📋 Match Details")

                # Gösterilecek kolonları seç
                display_columns = []
                if 'master_no' in results.columns:
                    display_columns.append('master_no')

                # Önemli eBay kolonları
                important_ebay_cols = ['ebay_order_number', 'ebay_buyer_name', 'ebay_item_title']
                for col in important_ebay_cols:
                    if col in results.columns:
                        display_columns.append(col)

                # Önemli Amazon kolonları
                important_amazon_cols = ['amazon_order_id', 'amazon_item_title']
                for col in important_amazon_cols:
                    if col in results.columns:
                        display_columns.append(col)

                # Kâr kolonları
                profit_cols = ['calculated_ebay_earning_usd', 'calculated_amazon_cost_usd', 'calculated_profit_usd']
                for col in profit_cols:
                    if col in results.columns:
                        display_columns.append(col)

                # Match info
                if 'match_score' in results.columns:
                    display_columns.append('match_score')

                # Tabloyu göster
                if display_columns:
                    st.dataframe(results[display_columns], use_container_width=True)
                else:
                    # Fallback - ilk 15 kolonu göster
                    display_cols = results.columns[:15]
                    st.dataframe(results[display_cols], use_container_width=True)

                # İndirme seçenekleri
                st.markdown("#### 💾 Download Results")

                col1, col2 = st.columns(2)

                with col1:
                    # JSON indirme
                    json_data = results.to_json(orient='records', indent=2)
                    if st.download_button(
                            label="📄 Download as JSON",
                            data=json_data,
                            file_name=f"matched_orders_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                            mime="application/json"
                    ):
                        st.success("✅ JSON file downloaded!")

                        # Session'dan tüm verileri sil
                        keys_to_remove = ['ebay_df', 'amazon_df', 'match_results']
                        for key in keys_to_remove:
                            if key in st.session_state:
                                del st.session_state[key]

                        st.info("🗑️ Data automatically cleaned - you can upload new files")
                        st.rerun()

                with col2:
                    # CSV indirme
                    csv_data = results.to_csv(index=False)
                    if st.download_button(
                            label="📊 Download as CSV",
                            data=csv_data,
                            file_name=f"matched_orders_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                            mime="text/csv"
                    ):
                        st.success("✅ CSV file downloaded!")

                        # Session'dan tüm verileri sil
                        keys_to_remove = ['ebay_df', 'amazon_df', 'match_results']
                        for key in keys_to_remove:
                            if key in st.session_state:
                                del st.session_state[key]

                        st.info("🗑️ Data automatically cleaned - you can upload new files")
                        st.rerun()

            else:
                st.warning("⚠️ No matches found")

    # Yardım bölümü
    st.markdown("---")
    with st.expander("❓ Enhanced Address Extraction Help"):
        st.markdown("""
        **🚀 Enhanced Amazon Format Support:**

        **✅ Supported Formats:**
        - **New Format:** `shippingAddress` object with structured fields
        - **Mixed Format:** String addresses within `shippingAddress`
        - **Old Format:** Direct `ship_to` field (legacy compatibility)

        **🔧 Address Extraction Features:**
        - Automatic format detection
        - Object/JSON parsing for new format
        - Individual component extraction (name, address, city, state, zip)
        - Proper address string building with newline separators
        - Fallback methods for incomplete data

        **💡 Matching Algorithm:**
        - **Name matching:** Fuzzy matching against full address
        - **Location matching:** City, state, and ZIP code verification
        - **Product matching:** Title similarity using multiple algorithms
        - **Date validation:** Ensures logical order timing
        - **Weighted scoring:** Configurable importance for each factor

        **📊 Quality Assurance:**
        - Pre-matching address quality check
        - Format detection and validation
        - Real-time progress tracking
        - Detailed error reporting

        **🎯 Tips for Best Results:**
        - Check "Address Quality Check" before matching
        - Use threshold 60-80% for balanced results
        - Higher thresholds = more precise but fewer matches
        - Lower thresholds = more matches but less precision
        """)

    # Footer
    st.caption("🔗 Order Matcher | Enhanced with smart address extraction for all Amazon formats")


if __name__ == "__main__":
    main()