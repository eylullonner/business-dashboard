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
        # SADECE eIS CO patterns (basit ve güvenilir)
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

        # Default thresholds for eIS CO matching
        self.name_threshold = 85  # High confidence for name matching
        self.product_threshold = 60  # Lower threshold for international

    def extract_amazon_shipping_address(self, amazon_order: Dict) -> str:
        """
        Extract shipping address from various Amazon formats
        """
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

        if not ebay_buyer or not amazon_address:
            return self._no_match_result()

        # Search for eIS CO patterns
        for pattern in self.eis_patterns:
            match = re.search(pattern, amazon_address, re.IGNORECASE)
            if match:
                extracted_name = match.group(1).strip()

                # Clean extracted name (remove warehouse codes)
                # "Jose Gonzalez EVTN NJQVNRC" → "Jose Gonzalez"
                cleaned_name = self._clean_extracted_name(extracted_name)

                # Calculate name similarity
                similarity = fuzz.ratio(ebay_buyer.lower(), cleaned_name.lower())

                if similarity >= self.name_threshold:
                    return {
                        'detected': True,
                        'pattern_type': 'eis_co',
                        'confidence': similarity,
                        'extracted_name': cleaned_name,
                        'original_extraction': extracted_name,
                        'match_pattern': pattern,
                        'ebay_buyer': ebay_buyer,
                        'is_international': self._is_international_order(ebay_order)
                    }

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

        Args:
            ebay_order: eBay order dict
            amazon_order: Amazon order dict
            title_similarity_func: Function to calculate product title similarity
            date_check_func: Function to validate date logic

        Returns:
            Match result dict with score and match status
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
        title_score = title_similarity_func(
            ebay_order.get('Item title', ''),
            amazon_order.get('item_title', '') or amazon_order.get('amazon_item_title', '')
        )

        # Validate with date logic
        date_valid, date_info, days_diff = date_check_func(
            ebay_order.get('Order creation date', ''),
            amazon_order.get('order_date', '') or amazon_order.get('orderDate', '')
        )

        # International matching logic
        if title_score >= self.product_threshold and date_valid:
            # Calculate final score (higher weight on name for international)
            final_score = min(95, eis_result['confidence'] * 0.7 + title_score * 0.3)

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
            # eIS CO detected but validation failed
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


# Test function for development
def test_international_matcher():
    """
    Test function for eIS CO pattern detection - SADECE eIS CO
    """
    matcher = InternationalMatcher()

    # Test case 1: Perfect eIS CO match
    ebay_order = {
        'Buyer name': 'Jose Gonzalez',
        'Ship to country': 'MX'
    }

    amazon_order = {
        'shippingAddress': {
            'name': 'eIS CO Jose Gonzalez'
        }
    }

    result = matcher.detect_eis_co_pattern(ebay_order, amazon_order)
    print("Test 1 - Perfect eIS CO Match:")
    print(f"Detected: {result['detected']}")
    print(f"Confidence: {result['confidence']}%")
    print(f"Extracted: {result.get('extracted_name', 'N/A')}")
    print()

    # Test case 2: eIS CO with warehouse info (realistic)
    amazon_order_2 = {
        'full_address': 'eIS CO Jose Maria Gonzalez\nEVTN NJQVNRC\n110 INTERNATIONALE BLVD'
    }

    ebay_order_2 = {
        'Buyer name': 'Jose Maria Gonzalez',
        'Ship to country': 'MX'
    }

    result_2 = matcher.detect_eis_co_pattern(ebay_order_2, amazon_order_2)
    print("Test 2 - eIS CO with Warehouse Info:")
    print(f"Detected: {result_2['detected']}")
    print(f"Confidence: {result_2['confidence']}%")
    print(f"Extracted: {result_2.get('extracted_name', 'N/A')}")
    print()

    # Test case 3: Case insensitive
    amazon_order_3 = {
        'shippingAddress': {
            'name': 'eis co Maria Santos'  # lowercase
        }
    }

    ebay_order_3 = {
        'Buyer name': 'Maria Santos',
        'Ship to country': 'MX'
    }

    result_3 = matcher.detect_eis_co_pattern(ebay_order_3, amazon_order_3)
    print("Test 3 - Case Insensitive:")
    print(f"Detected: {result_3['detected']}")
    print(f"Confidence: {result_3['confidence']}%")
    print(f"Extracted: {result_3.get('extracted_name', 'N/A')}")


if __name__ == "__main__":
    test_international_matcher()