# utils/exchange_rate_handler.py - Rate Limited Versiyonu

import requests
import streamlit as st
import re
import time
from datetime import datetime, timedelta
from typing import Dict, Optional, Tuple


class ExchangeRateHandler:
    """
    Rate-limited Frankfurter API handler
    Günlük limit: ~1000 request, burst: 10/saniye
    """

    def __init__(self):
        self.base_url = "https://api.frankfurter.app"
        self.cache_key = "exchange_rate_cache"
        self.max_cache_age_days = 30  # Uzun cache - API tasarrufu
        self.last_request_time = 0
        self.min_request_interval = 0.2  # 200ms minimum gap
        self.daily_request_count_key = "api_request_count"
        self.max_daily_requests = 900  # Güvenlik marjı

        # Cache'i initialize et
        if self.cache_key not in st.session_state:
            st.session_state[self.cache_key] = {}

        # Daily counter initialize
        if self.daily_request_count_key not in st.session_state:
            st.session_state[self.daily_request_count_key] = {
                'count': 0,
                'date': datetime.now().strftime('%Y-%m-%d')
            }

    def check_daily_limit(self) -> bool:
        """Günlük API limit kontrolü"""
        today = datetime.now().strftime('%Y-%m-%d')
        counter = st.session_state[self.daily_request_count_key]

        # Yeni gün ise counter'ı reset et
        if counter['date'] != today:
            counter['count'] = 0
            counter['date'] = today

        return counter['count'] < self.max_daily_requests

    def increment_request_count(self):
        """API request sayacını artır"""
        counter = st.session_state[self.daily_request_count_key]
        counter['count'] += 1

    def rate_limit_delay(self):
        """Rate limiting - requestler arası minimum bekleme"""
        current_time = time.time()
        elapsed = current_time - self.last_request_time

        if elapsed < self.min_request_interval:
            wait_time = self.min_request_interval - elapsed
            print(f"⏳ Rate limiting: waiting {wait_time:.2f}s...")
            time.sleep(wait_time)

        self.last_request_time = time.time()

    def get_cached_rate(self, date_str: str, from_currency: str = "USD", to_currency: str = "TRY") -> Optional[float]:
        """Cache'den kur al - uzun cache süresi"""
        cache = st.session_state[self.cache_key]
        cache_key = f"{date_str}_{from_currency}_{to_currency}"

        if cache_key in cache:
            cached_data = cache[cache_key]
            try:
                cache_date = datetime.fromisoformat(cached_data['cached_at'])
                if (datetime.now() - cache_date).days <= self.max_cache_age_days:
                    return cached_data['rate']
                else:
                    del cache[cache_key]
            except:
                del cache[cache_key]

        return None

    def cache_rate(self, date_str: str, rate: float, from_currency: str = "USD", to_currency: str = "TRY"):
        """Kuru cache'le - uzun süre sakla"""
        cache = st.session_state[self.cache_key]
        cache_key = f"{date_str}_{from_currency}_{to_currency}"

        cache[cache_key] = {
            'rate': rate,
            'cached_at': datetime.now().isoformat(),
            'date': date_str,
            'from': from_currency,
            'to': to_currency
        }

        # Cache temizleme (daha büyük cache - API tasarrufu)
        if len(cache) > 200:
            try:
                sorted_cache = sorted(cache.items(), key=lambda x: x[1]['cached_at'])
                for i in range(50):  # 50 tane sil
                    if i < len(sorted_cache):
                        del cache[sorted_cache[i][0]]
            except:
                st.session_state[self.cache_key] = {}

    def fetch_rate_from_frankfurter(self, date_str: str = None, from_currency: str = "USD", to_currency: str = "TRY") -> \
    Tuple[bool, Optional[float], str]:
        """
        Rate-limited Frankfurter API call
        """
        # Daily limit kontrolü
        if not self.check_daily_limit():
            counter = st.session_state[self.daily_request_count_key]
            print(f"❌ Daily API limit reached: {counter['count']}/{self.max_daily_requests}")
            return False, None, f"Daily API limit reached ({counter['count']}/{self.max_daily_requests})"

        try:
            # Rate limiting
            self.rate_limit_delay()

            # URL oluştur
            if date_str:
                url = f"{self.base_url}/{date_str}?from={from_currency}&to={to_currency}"
            else:
                url = f"{self.base_url}/latest?from={from_currency}&to={to_currency}"

            counter = st.session_state[self.daily_request_count_key]
            print(f"🌐 API Request ({counter['count'] + 1}/{self.max_daily_requests}): {url}")

            response = requests.get(url, timeout=10)

            # Request count'ı artır
            self.increment_request_count()

            print(f"📡 Response: {response.status_code}")

            if response.status_code == 200:
                data = response.json()

                if 'rates' in data and to_currency in data['rates']:
                    rate = float(data['rates'][to_currency])
                    rate_type = "historical" if date_str else "current"
                    print(f"✅ Success: 1 {from_currency} = {rate} {to_currency} ({rate_type})")
                    return True, rate, f"Frankfurter API ({rate_type} rate)"
                else:
                    return False, None, f"Currency {to_currency} not found"

            elif response.status_code == 429:
                print("❌ Rate limit exceeded!")
                return False, None, "API rate limit exceeded - try again later"

            elif response.status_code == 404:
                return False, None, f"No data available for date {date_str}"

            else:
                return False, None, f"API error: HTTP {response.status_code}"

        except requests.exceptions.Timeout:
            return False, None, "API request timeout"

        except requests.exceptions.ConnectionError:
            return False, None, "Cannot connect to API"

        except Exception as e:
            return False, None, f"Unexpected error: {str(e)}"

    def get_exchange_rate(self, date_str: str = None, from_currency: str = "USD", to_currency: str = "TRY") -> Tuple[
        bool, Optional[float], str]:
        """
        Ana kur alma fonksiyonu - cache-first approach
        """
        # Tarih yoksa bugünkü tarih
        if not date_str:
            date_str = datetime.now().strftime('%Y-%m-%d')

        print(f"💱 Getting exchange rate for {date_str}: {from_currency} → {to_currency}")

        # ÖNCE CACHE'E BAK - uzun cache süresi sayesinde çoğu request cache'den gelir
        cached_rate = self.get_cached_rate(date_str, from_currency, to_currency)
        if cached_rate is not None:
            print(f"📦 Cache hit: 1 {from_currency} = {cached_rate} {to_currency}")
            return True, cached_rate, f"Rate loaded from cache for {date_str}"

        print("🔍 Cache miss, checking API limits...")

        # Daily limit kontrolü
        if not self.check_daily_limit():
            print("❌ Daily limit reached, using fixed rate...")
            # Limit aşıldıysa sabit kur kullan
            if to_currency == "TRY" and from_currency == "USD":
                rate = 35.0  # Güncel ortalama
                self.cache_rate(date_str, rate, from_currency, to_currency)
                return True, rate, "Fixed rate (daily API limit reached)"

        # API'den çek
        success, rate, message = self.fetch_rate_from_frankfurter(date_str, from_currency, to_currency)

        # Historical başarısızsa current dene
        if not success and date_str:
            print("🔄 Historical failed, trying current rate...")
            success, rate, message = self.fetch_rate_from_frankfurter(None, from_currency, to_currency)
            if success:
                message += " (historical not available, using current)"

        # API tamamen başarısızsa sabit kur
        if not success:
            print("🔄 API failed, using fixed rate...")
            if to_currency == "TRY" and from_currency == "USD":
                rate = 35.0
                success = True
                message = "Fixed fallback rate (API unavailable)"

        if success and rate is not None:
            # Uzun süreli cache - API tasarrufu
            self.cache_rate(date_str, rate, from_currency, to_currency)
            return True, rate, f"{message} (cached for 30 days)"
        else:
            return False, None, message or "Rate fetching failed"

    def convert_currency(self, amount: float, rate: float) -> float:
        """Para birimi çevrimi"""
        return amount / rate

    def parse_try_amount(self, try_string: str) -> Optional[float]:
        """TRY string'ini parse et"""
        if not try_string:
            return None

        try_clean = str(try_string).replace('TRY', '').replace('₺', '').strip()

        try:
            if ',' in try_clean and '.' in try_clean:
                try_clean = try_clean.replace(',', '')
            elif ',' in try_clean and '.' not in try_clean:
                try_clean = try_clean.replace(',', '.')

            return float(try_clean)
        except (ValueError, TypeError):
            return None

    def parse_date_for_api(self, date_input) -> Optional[str]:
        """Tarih formatını YYYY-MM-DD'ye çevir"""
        if not date_input:
            return None

        try:
            if hasattr(date_input, 'strftime'):
                return date_input.strftime('%Y-%m-%d')

            date_str = str(date_input).strip()

            if re.match(r'^\d{4}-\d{2}-\d{2}$', date_str):
                return date_str

            formats = [
                '%Y-%m-%d', '%m/%d/%Y', '%d/%m/%Y', '%Y/%m/%d',
                '%B %d, %Y', '%b %d, %Y', '%d %B %Y', '%d %b %Y'
            ]

            for fmt in formats:
                try:
                    parsed = datetime.strptime(date_str, fmt)
                    return parsed.strftime('%Y-%m-%d')
                except ValueError:
                    continue

        except Exception:
            return None

        return None

    def calculate_amazon_cost_usd(self, order_total_try: str, order_date: str) -> Tuple[bool, Optional[float], str]:
        """Amazon TRY siparişini USD'ye çevir"""
        print(f"🧮 Calculating: {order_total_try} on {order_date}")

        try_amount = self.parse_try_amount(order_total_try)
        if try_amount is None:
            return False, None, f"Could not parse TRY amount: {order_total_try}"

        api_date = self.parse_date_for_api(order_date)
        if api_date is None:
            return False, None, f"Could not parse date: {order_date}"

        success, rate, rate_message = self.get_exchange_rate(api_date)
        if not success:
            return False, None, f"Exchange rate error: {rate_message}"

        usd_cost = self.convert_currency(try_amount, rate)

        return True, round(usd_cost, 2), f"TRY {try_amount:,.2f} → ${usd_cost:.2f} (rate: {rate:.4f})"

    def get_api_usage_stats(self) -> Dict:
        """API kullanım istatistikleri"""
        counter = st.session_state.get(self.daily_request_count_key, {'count': 0, 'date': 'unknown'})
        cache_stats = self.get_cache_stats()

        return {
            'daily_requests': counter['count'],
            'daily_limit': self.max_daily_requests,
            'remaining_requests': self.max_daily_requests - counter['count'],
            'date': counter['date'],
            'cache_entries': cache_stats['total_entries'],
            'cache_hit_potential': f"{(cache_stats['total_entries'] / max(1, counter['count']) * 100):.1f}%"
        }

    def get_cache_stats(self) -> Dict:
        """Cache istatistikleri"""
        cache = st.session_state.get(self.cache_key, {})

        if not cache:
            return {'total_entries': 0, 'date_range': 'No data'}

        dates = []
        for value in cache.values():
            try:
                dates.append(value['date'])
            except:
                continue

        return {
            'total_entries': len(cache),
            'date_range': f"{min(dates)} to {max(dates)}" if dates else 'No data'
        }

    def clear_cache(self):
        """Cache'i temizle"""
        st.session_state[self.cache_key] = {}

    def reset_daily_counter(self):
        """Günlük sayacı sıfırla (debug için)"""
        st.session_state[self.daily_request_count_key] = {
            'count': 0,
            'date': datetime.now().strftime('%Y-%m-%d')
        }


# Test fonksiyonu
def test_rate_limited_handler():
    """Rate limited handler test"""
    handler = ExchangeRateHandler()

    print("🧪 Testing Rate Limited Exchange Handler...")
    print("=" * 50)

    # API usage stats
    stats = handler.get_api_usage_stats()
    print(f"\n📊 API Usage Stats:")
    print(f"   Daily requests: {stats['daily_requests']}/{stats['daily_limit']}")
    print(f"   Remaining: {stats['remaining_requests']}")
    print(f"   Cache entries: {stats['cache_entries']}")

    # Test multiple requests (cache efficiency)
    test_dates = ["2024-12-15", "2024-12-16", "2024-12-17", "2024-12-15"]  # Son birinde cache hit olmalı

    for i, date in enumerate(test_dates, 1):
        print(f"\n{i}️⃣ Testing date: {date}")
        success, rate, message = handler.get_exchange_rate(date)
        if success:
            print(f"✅ {message}")
            print(f"💱 {date}: 1 USD = {rate:.4f} TRY")
        else:
            print(f"❌ {message}")

    # Updated stats
    final_stats = handler.get_api_usage_stats()
    print(f"\n📊 Final API Usage:")
    print(f"   Requests made: {final_stats['daily_requests']}")
    print(f"   Cache entries: {final_stats['cache_entries']}")


if __name__ == "__main__":
    test_rate_limited_handler()