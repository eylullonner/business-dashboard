# utils/international_matcher.py
"""
International Dropshipping Matcher Module
Handles eIS CO and other international warehouse patterns
"""

import re
from typing import Dict, Optional
from fuzzywuzzy import fuzz


class InternationalMatcher:
    """
    Specialized matcher for international dropshipping patterns
    Focus: eIS CO warehouse routing detection and matching
    """

    def __init__(self):
        # Yaygın tarih formatları
        self.eis_patterns = [
            r'eIS\s+CO\s+(.+)',  # "eIS CO Jose Gonzalez"
            r'eis\s+co\s+(.+)',  # "eis co Jose Gonzalez"
            r'EIS\s+CO\s+(.+)',  # "EIS CO Jose Gonzalez"
        ]

        # International countries (non-US)
        self.international_countries = {
            'MX', 'CA', 'BR', 'AR', 'CL', 'CO', 'PE', 'AU', 'NZ',
            'GB', 'DE', 'FR', 'IT', 'ES', 'JP', 'KR', 'IN'
        }

        # YENİ EŞIK DEĞERLERİ:
        self.name_threshold = 95  # %95'e çıkarıldı
        self.product_threshold = 50  # Aynı kaldı

    def extract_amazon_shipping_address(self, amazon_order: Dict) -> str:
        # YENİ EKLENEN DEBUG SATIRLARI:
        print(f"🔍 Amazon order keys: {list(amazon_order.keys())}")

        if 'shippingAddress' in amazon_order:
            shipping = amazon_order['shippingAddress']
            print(f"🔍 shippingAddress içeriği: {shipping}")
            if isinstance(shipping, dict) and 'name' in shipping:
                print(f"📝 Name bulundu: {shipping['name']}")
        # Try different address fields
        address_fields = [
            'full_address',
            'shipping_address',
            'ship_to'
        ]

        for field in address_fields:
            if field in amazon_order and amazon_order[field]:
                return str(amazon_order[field])

        # Try shippingAddress object
        if 'shippingAddress' in amazon_order:
            shipping_obj = amazon_order['shippingAddress']
            if isinstance(shipping_obj, dict):
                if 'name' in shipping_obj and shipping_obj['name']:
                    return str(shipping_obj['name'])
                elif 'fullAddress' in shipping_obj and shipping_obj['fullAddress']:
                    return str(shipping_obj['fullAddress'])

        return ""

    def detect_eis_co_pattern(self, ebay_order: Dict, amazon_order: Dict) -> Dict:
        """
        Detect eIS CO international pattern: "eIS CO [Buyer Name]"
        Returns high-confidence match info if pattern detected
        """
        ebay_buyer = ebay_order.get('Buyer name', '').strip()
        amazon_address = self.extract_amazon_shipping_address(amazon_order)

        # DETAILED DEBUG FOR ALL eIS CO ATTEMPTS
        if 'eIS CO' in str(amazon_address):
            print(f"🌍 eIS CO DETECTION ATTEMPT:")
            print(f"   eBay Buyer: '{ebay_buyer}'")
            print(f"   Amazon Address: '{amazon_address}'")

        if not ebay_buyer or not amazon_address:
            return self._no_match_result()

        # Search for eIS CO patterns
        for pattern in self.eis_patterns:
            match = re.search(pattern, amazon_address, re.IGNORECASE)
            if match:
                extracted_name = match.group(1).strip()
                cleaned_name = self._clean_extracted_name(extracted_name)

                print(f"   ✅ Pattern matched: {pattern}")
                print(f"   📝 Raw extracted: '{extracted_name}'")
                print(f"   🧹 Cleaned name: '{cleaned_name}'")

                # Calculate similarity
                similarity = fuzz.ratio(ebay_buyer.lower(), cleaned_name.lower())
                partial_similarity = fuzz.partial_ratio(ebay_buyer.lower(), cleaned_name.lower())
                token_similarity = fuzz.token_set_ratio(ebay_buyer.lower(), cleaned_name.lower())

                print(f"   📊 Similarity Scores:")
                print(f"      - Ratio: {similarity}%")
                print(f"      - Partial: {partial_similarity}%")
                print(f"      - Token: {token_similarity}%")
                print(f"      - Threshold: {self.name_threshold}%")

                # Use the highest score
                best_similarity = max(similarity, partial_similarity, token_similarity)

                if best_similarity >= self.name_threshold:
                    print(f"   ✅ MATCH SUCCESS! Best score: {best_similarity}%")
                    return {
                        'detected': True,
                        'pattern_type': 'eis_co',
                        'confidence': best_similarity,
                        'extracted_name': cleaned_name,
                        'original_extraction': extracted_name,
                        'match_pattern': pattern,
                        'ebay_buyer': ebay_buyer,
                        'is_international': self._is_international_order(ebay_order)
                    }
                else:
                    print(f"   ❌ Below threshold: {best_similarity}% < {self.name_threshold}%")

        if 'eIS CO' in str(amazon_address):
            print(f"   ❌ eIS CO pattern found but no regex match")

        return self._no_match_result()

    def _clean_extracted_name(self, extracted_name: str) -> str:
        """
        Clean extracted name from eIS CO address - BASIT VERSİYON
        Sadece first line'ı al, warehouse kodlarını ignore et
        """
        # İlk satırı al (newline'dan önce)
        first_line = extracted_name.split('\n')[0].strip()

        # Basit temizlik: sadece harf ve space
        cleaned = re.sub(r'[^a-zA-Z\s]', ' ', first_line)
        cleaned = re.sub(r'\s+', ' ', cleaned).strip()

        # İlk 2-3 kelimeyi al (isim olarak makul)
        words = cleaned.split()
        if len(words) >= 2:
            return ' '.join(words[:3])  # Max 3 kelime (First Middle Last)
        else:
            return cleaned

    def _is_international_order(self, ebay_order: Dict) -> bool:
        """
        Check if eBay order is international (non-US)
        """
        country = ebay_order.get('Ship to country', '').upper()
        return country in self.international_countries

    def _no_match_result(self) -> Dict:
        """
        Standard no-match result
        """
        return {
            'detected': False,
            'pattern_type': None,
            'confidence': 0,
            'is_international': False
        }

    def calculate_international_match_score(self, ebay_order: Dict, amazon_order: Dict,
                                            title_similarity_func, date_check_func) -> Dict:
        """
        Calculate match score for international orders using eIS CO pattern
        """
        # Detect eIS CO pattern
        eis_result = self.detect_eis_co_pattern(ebay_order, amazon_order)

        if not eis_result['detected']:
            return {
                'total_score': 0,
                'is_match': False,
                'match_method': 'international_no_pattern'
            }

        print(f"🌍 eIS CO Pattern Detected! Confidence: {eis_result['confidence']}%")
        print(f"   eBay Buyer: {eis_result['ebay_buyer']}")
        print(f"   Extracted: {eis_result['extracted_name']}")

        # Validate with product similarity
        ebay_title = ebay_order.get('Item title', '')
        amazon_title = amazon_order.get('item_title', '') or amazon_order.get('amazon_item_title', '')

        print(f"🔍 PRODUCT VALIDATION:")
        print(f"   eBay title: '{ebay_title}'")
        print(f"   Amazon title: '{amazon_title}'")

        title_score = title_similarity_func(ebay_title, amazon_title)
        print(f"   📊 Product similarity: {title_score}% (Threshold: {self.product_threshold}%)")

        # Validate with date logic
        ebay_date = ebay_order.get('Order creation date', '')
        amazon_date = amazon_order.get('order_date', '') or amazon_order.get('orderDate', '')

        print(f"🔍 DATE VALIDATION:")
        print(f"   eBay date: '{ebay_date}'")
        print(f"   Amazon date: '{amazon_date}'")

        date_valid, date_info, days_diff = date_check_func(ebay_date, amazon_date)
        print(f"   📅 Date valid: {date_valid} ({date_info}) - Diff: {days_diff} days")

        # International matching logic
        if title_score >= self.product_threshold and date_valid:
            final_score = min(95, eis_result['confidence'] * 0.7 + title_score * 0.3)

            print(f"🎉 VALIDATION SUCCESS!")
            print(f"   📊 Final score: {final_score}")

            return {
                'total_score': final_score,
                'is_match': True,
                'match_method': 'eis_co_international',
                'international_info': eis_result,
                'title_score': title_score,
                'date_status': date_info,
                'days_difference': days_diff
            }
        else:
            print(f"❌ VALIDATION FAILED!")
            print(f"   Product: {title_score}% >= {self.product_threshold}% ? {title_score >= self.product_threshold}")
            print(f"   Date: {date_valid}")

            return {
                'total_score': 0,
                'is_match': False,
                'match_method': 'eis_co_validation_failed',
                'international_info': eis_result,
                'title_score': title_score,
                'date_status': date_info,
                'validation_failure': f"Title: {title_score}%, Date: {date_valid}"
            }

    def get_international_stats(self, matches_df) -> Dict:
        """
        Get statistics about international vs domestic matches
        """
        if matches_df.empty:
            return {
                'total_matches': 0,
                'international_matches': 0,
                'domestic_matches': 0,
                'international_percentage': 0
            }

        # Count international matches
        international_matches = len(matches_df[
                                        matches_df.get('match_method', '') == 'eis_co_international'
                                        ])
        total_matches = len(matches_df)

        return {
            'total_matches': total_matches,
            'international_matches': international_matches,
            'domestic_matches': total_matches - international_matches,
            'international_percentage': (international_matches / total_matches * 100) if total_matches > 0 else 0
        }

    def update_thresholds(self, name_threshold: int = None, product_threshold: int = None):
        """
        Update matching thresholds for fine-tuning
        """
        if name_threshold is not None:
            self.name_threshold = name_threshold
        if product_threshold is not None:
            self.product_threshold = product_threshold

        print(f"📊 International thresholds updated: Name={self.name_threshold}%, Product={self.product_threshold}%")