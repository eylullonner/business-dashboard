# utils/international_matcher.py - YENİ MODÜLER VERSİYON
"""
Modular International eIS CO Matcher
Clean and simple implementation for eIS CO warehouse routing detection
"""

import re
from typing import Dict, Optional, Tuple
from fuzzywuzzy import fuzz


class InternationalMatcher:
    """
    Modular matcher for international dropshipping patterns
    Focus: eIS CO warehouse routing detection and matching
    """

    def __init__(self):
        # Configuration - OPTIMIZED VALUES
        self.config = {
            'name_threshold': 85,  # Optimized: Name similarity threshold
            'product_threshold': 50,  # Optimized: Product similarity threshold
            'enable_debug': False  # Debug output (default off)
        }

        # eIS CO patterns
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

    def update_config(self, **kwargs):
        """Update configuration parameters"""
        self.config.update(kwargs)

    def debug_log(self, message: str):
        """Debug logging"""
        if self.config['enable_debug']:
            print(f"🌍 eIS CO DEBUG: {message}")

    # ========== CORE EXTRACTION FUNCTIONS ==========

    def extract_amazon_address(self, amazon_order: Dict) -> str:
        """
        Extract shipping address from Amazon order
        Handles multiple field formats
        """
        address = ""

        # Method 1: shippingAddress object
        if 'shippingAddress' in amazon_order:
            shipping = amazon_order['shippingAddress']
            if isinstance(shipping, dict):
                # Try name field first
                if 'name' in shipping and shipping['name']:
                    address = str(shipping['name'])
                # Try fullAddress as fallback
                elif 'fullAddress' in shipping and shipping['fullAddress']:
                    address = str(shipping['fullAddress'])

        # Method 2: ship_to field (legacy)
        if not address and 'ship_to' in amazon_order:
            address = str(amazon_order['ship_to'])

        # Method 3: direct address fields
        if not address:
            address_parts = []
            for field in ['buyer_name', 'recipient_name', 'customer_name']:
                if field in amazon_order and amazon_order[field]:
                    address_parts.append(str(amazon_order[field]))
            address = ' '.join(address_parts)

        self.debug_log(f"Extracted address: '{address}'")
        return address.strip()

    def extract_ebay_buyer(self, ebay_order: Dict) -> str:
        """Extract buyer name from eBay order"""
        buyer = ""

        # Try different field names
        for field in ['Buyer name', 'buyer_name', 'buyerName', 'recipient_name']:
            if field in ebay_order and ebay_order[field]:
                buyer = str(ebay_order[field]).strip()
                break

        self.debug_log(f"eBay buyer: '{buyer}'")
        return buyer

    def extract_ebay_country(self, ebay_order: Dict) -> str:
        """Extract shipping country from eBay order"""
        country = ""

        for field in ['Ship to country', 'ship_country', 'country']:
            if field in ebay_order and ebay_order[field]:
                country = str(ebay_order[field]).upper()
                break

        return country

    # ========== eIS CO PATTERN DETECTION ==========

    def detect_eis_pattern(self, amazon_address: str) -> Optional[str]:
        """
        Detect eIS CO pattern in Amazon address
        Returns extracted customer name or None
        """
        if not amazon_address:
            return None

        self.debug_log(f"Checking for eIS CO pattern in: '{amazon_address}'")

        # Try each pattern
        for pattern in self.eis_patterns:
            match = re.search(pattern, amazon_address, re.IGNORECASE)
            if match:
                raw_extracted = match.group(1).strip()
                cleaned_name = self.clean_extracted_name(raw_extracted)

                self.debug_log(f"Pattern matched: {pattern}")
                self.debug_log(f"Raw extracted: '{raw_extracted}'")
                self.debug_log(f"Cleaned name: '{cleaned_name}'")

                return cleaned_name

        return None

    def clean_extracted_name(self, raw_name: str) -> str:
        """
        Clean extracted name from eIS CO address
        Simple cleaning - just take first line and clean chars
        """
        if not raw_name:
            return ""

        # Take first line only
        first_line = raw_name.split('\n')[0].strip()

        # Remove non-alphabetic characters except spaces
        cleaned = re.sub(r'[^a-zA-Z\s]', ' ', first_line)

        # Remove extra spaces and take max 3 words
        words = cleaned.split()
        result = ' '.join(words[:3]) if words else ""

        return result

    # ========== SIMILARITY CALCULATION ==========

    def calculate_name_similarity(self, ebay_buyer: str, extracted_name: str) -> int:
        """
        Calculate name similarity using multiple fuzzy algorithms
        Returns best score from different methods
        """
        if not ebay_buyer or not extracted_name:
            return 0

        ebay_clean = ebay_buyer.lower().strip()
        extracted_clean = extracted_name.lower().strip()

        # Multiple similarity methods
        ratio_score = fuzz.ratio(ebay_clean, extracted_clean)
        partial_score = fuzz.partial_ratio(ebay_clean, extracted_clean)
        token_score = fuzz.token_set_ratio(ebay_clean, extracted_clean)

        # Return best score
        best_score = max(ratio_score, partial_score, token_score)

        self.debug_log(f"Name similarity: {ebay_buyer} vs {extracted_name}")
        self.debug_log(f"  Ratio: {ratio_score}%")
        self.debug_log(f"  Partial: {partial_score}%")
        self.debug_log(f"  Token: {token_score}%")
        self.debug_log(f"  Best: {best_score}%")

        return best_score

    # ========== PRODUCT VALIDATION ==========

    def extract_product_title(self, order: Dict, source: str) -> str:
        """Extract product title from order (eBay or Amazon)"""
        title = ""

        if source == "ebay":
            fields = ['Item title', 'item_title', 'title', 'product_name']
        else:  # amazon
            # Try products array first
            if 'products' in order and isinstance(order['products'], list) and len(order['products']) > 0:
                product = order['products'][0]
                if isinstance(product, dict) and 'title' in product:
                    title = str(product['title'])

            # Fallback to direct fields
            if not title:
                fields = ['item_title', 'product_title', 'title', 'itemTitle']
            else:
                return title

        # Extract from fields
        for field in fields:
            if field in order and order[field]:
                title = str(order[field])
                break

        return title

    def calculate_product_similarity(self, ebay_order: Dict, amazon_order: Dict) -> int:
        """Calculate product title similarity"""
        ebay_title = self.extract_product_title(ebay_order, "ebay")
        amazon_title = self.extract_product_title(amazon_order, "amazon")

        if not ebay_title or not amazon_title:
            self.debug_log(f"Missing product titles: eBay='{ebay_title}', Amazon='{amazon_title}'")
            return 0

        # Simple token ratio
        similarity = fuzz.token_set_ratio(ebay_title.lower(), amazon_title.lower())

        self.debug_log(f"Product similarity: {similarity}%")
        self.debug_log(f"  eBay: '{ebay_title[:50]}...'")
        self.debug_log(f"  Amazon: '{amazon_title[:50]}...'")

        return similarity

    # ========== DATE VALIDATION ==========

    def extract_date(self, order: Dict, source: str) -> str:
        """Extract order date"""
        date = ""

        if source == "ebay":
            fields = ['Order creation date', 'order_date', 'creation_date', 'date']
        else:  # amazon
            fields = ['orderDate', 'order_date', 'order_placed', 'date']

        for field in fields:
            if field in order and order[field]:
                date = str(order[field])
                break

        return date

    def validate_dates(self, ebay_order: Dict, amazon_order: Dict) -> Tuple[bool, str]:
        """
        Simple date validation
        For now, just return True (skip date validation)
        """
        ebay_date = self.extract_date(ebay_order, "ebay")
        amazon_date = self.extract_date(amazon_order, "amazon")

        self.debug_log(f"Date validation: eBay='{ebay_date}', Amazon='{amazon_date}'")

        # For now, skip strict date validation
        return True, "date_validation_skipped"

    # ========== MAIN MATCHING FUNCTION ==========

    def match_international_order(self, ebay_order: Dict, amazon_order: Dict) -> Dict:
        """
        Main function to match international eIS CO orders
        Returns match result with details
        """
        self.debug_log("=== Starting international match ===")

        # Step 1: Extract data
        amazon_address = self.extract_amazon_address(amazon_order)
        ebay_buyer = self.extract_ebay_buyer(ebay_order)
        ebay_country = self.extract_ebay_country(ebay_order)

        if not amazon_address or not ebay_buyer:
            self.debug_log("Missing address or buyer info")
            return self.create_no_match_result("missing_data")

        # Step 2: Check if international
        is_international = ebay_country in self.international_countries
        self.debug_log(f"Order country: {ebay_country}, International: {is_international}")

        # Step 3: Detect eIS CO pattern
        extracted_name = self.detect_eis_pattern(amazon_address)
        if not extracted_name:
            self.debug_log("No eIS CO pattern detected")
            return self.create_no_match_result("no_eis_pattern")

        # Step 4: Calculate name similarity
        name_similarity = self.calculate_name_similarity(ebay_buyer, extracted_name)
        name_match = name_similarity >= self.config['name_threshold']

        if not name_match:
            self.debug_log(f"Name similarity too low: {name_similarity}% < {self.config['name_threshold']}%")
            return self.create_no_match_result("name_threshold_failed", {
                'name_similarity': name_similarity,
                'extracted_name': extracted_name
            })

        # Step 5: Validate product similarity
        product_similarity = self.calculate_product_similarity(ebay_order, amazon_order)
        product_match = product_similarity >= self.config['product_threshold']

        if not product_match:
            self.debug_log(f"Product similarity too low: {product_similarity}% < {self.config['product_threshold']}%")
            return self.create_no_match_result("product_threshold_failed", {
                'product_similarity': product_similarity
            })

        # Step 6: Date validation
        date_valid, date_info = self.validate_dates(ebay_order, amazon_order)

        if not date_valid:
            self.debug_log(f"Date validation failed: {date_info}")
            return self.create_no_match_result("date_validation_failed", {
                'date_info': date_info
            })

        # SUCCESS!
        self.debug_log("🎉 INTERNATIONAL MATCH SUCCESS!")

        return {
            'is_match': True,
            'match_method': 'eis_co_international',
            'confidence': min(95, (name_similarity + product_similarity) / 2),
            'international_info': {
                'extracted_name': extracted_name,
                'name_similarity': name_similarity,
                'product_similarity': product_similarity,
                'ebay_country': ebay_country,
                'is_international': is_international
            },
            'total_score': min(95, (name_similarity + product_similarity) / 2),
            'date_status': date_info,
            'days_difference': 0  # Skip for now
        }

    def create_no_match_result(self, reason: str, extra_data: Dict = None) -> Dict:
        """Create standardized no-match result"""
        result = {
            'is_match': False,
            'match_method': 'eis_co_no_match',
            'confidence': 0,
            'reason': reason,
            'total_score': 0,
            'date_status': 'not_checked',
            'days_difference': 999
        }

        if extra_data:
            result.update(extra_data)

        return result

    # ========== PUBLIC API ==========

    def calculate_international_match_score(self, ebay_order: Dict, amazon_order: Dict,
                                            title_similarity_func=None, date_check_func=None) -> Dict:
        """
        Public API function for compatibility with existing code
        """
        return self.match_international_order(ebay_order, amazon_order)

    def update_thresholds(self, name_threshold: int = None, product_threshold: int = None):
        """Update matching thresholds"""
        if name_threshold is not None:
            self.config['name_threshold'] = name_threshold
        if product_threshold is not None:
            self.config['product_threshold'] = product_threshold

        self.debug_log(
            f"Thresholds updated: Name={self.config['name_threshold']}%, Product={self.config['product_threshold']}%")

    def enable_debug(self, enable: bool = True):
        """Enable/disable debug output"""
        self.config['enable_debug'] = enable

    def get_statistics(self) -> Dict:
        """Get current configuration and statistics"""
        return {
            'name_threshold': self.config['name_threshold'],
            'product_threshold': self.config['product_threshold'],
            'debug_enabled': self.config['enable_debug'],
            'supported_countries': len(self.international_countries),
            'eis_patterns': len(self.eis_patterns)
        }