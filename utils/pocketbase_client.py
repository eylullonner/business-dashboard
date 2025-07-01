import requests
import streamlit as st
from config import POCKETBASE_URL, COLLECTION_NAME, POCKETBASE_TOKEN, CACHE_TTL


def get_headers():
    """PocketBase için headers döndür"""
    headers = {"Content-Type": "application/json"}
    if POCKETBASE_TOKEN:
        headers["Authorization"] = f"Bearer {POCKETBASE_TOKEN}"
    return headers


@st.cache_data(ttl=CACHE_TTL)
def get_all_data():
    """PocketBase'den tüm veriyi çek (cache'li)"""
    all_data = []
    page = 1
    max_pages = 100  # Güvenlik limiti

    try:
        while page <= max_pages:
            response = requests.get(
                f"{POCKETBASE_URL}/api/collections/{COLLECTION_NAME}/records",
                params={"page": page, "perPage": 100},
                headers=get_headers(),
                timeout=10
            )

            if response.status_code != 200:
                if response.status_code == 404:
                    st.error(f"❌ Collection '{COLLECTION_NAME}' not found")
                elif response.status_code == 401:
                    st.error("❌ Authentication failed - check your token")
                else:
                    st.error(f"❌ PocketBase error: {response.status_code}")
                break

            data = response.json()
            items = data.get("items", [])

            if not items:
                break

            all_data.extend(items)

            # Eğer son sayfa ise dur
            if len(items) < 100:
                break

            page += 1

        return all_data

    except requests.exceptions.ConnectionError:
        st.error(f"❌ Cannot connect to PocketBase at {POCKETBASE_URL}")
        return []
    except requests.exceptions.Timeout:
        st.error("❌ PocketBase request timeout")
        return []
    except Exception as e:
        st.error(f"❌ Error loading data: {str(e)}")
        return []


def upload_record(record):
    """Tek kayıt yükle - ENHANCED DEBUG"""
    try:
        print(f"DEBUG - Uploading record with keys: {list(record.keys())}")
        print(f"DEBUG - Record data: {record}")

        response = requests.post(
            f"{POCKETBASE_URL}/api/collections/{COLLECTION_NAME}/records",
            json=record,
            headers=get_headers(),
            timeout=10
        )

        print(f"DEBUG - Response status: {response.status_code}")
        print(f"DEBUG - Response headers: {dict(response.headers)}")

        if response.status_code == 200:
            return True, response.json()
        else:
            # Detailed error logging
            error_msg = response.text
            print(f"DEBUG - Raw error response: {error_msg}")

            try:
                error_data = response.json()
                print(f"DEBUG - Parsed error data: {error_data}")

                # Extract specific field errors
                if 'data' in error_data:
                    field_errors = error_data['data']
                    print(f"DEBUG - Field errors: {field_errors}")
                    error_msg = f"Field validation errors: {field_errors}"
                else:
                    error_msg = error_data.get('message', error_msg)
            except Exception as parse_error:
                print(f"DEBUG - Could not parse error JSON: {parse_error}")
                pass

            return False, error_msg

    except requests.exceptions.ConnectionError as e:
        print(f"DEBUG - Connection error: {e}")
        return False, f"Cannot connect to PocketBase at {POCKETBASE_URL}"
    except requests.exceptions.Timeout as e:
        print(f"DEBUG - Timeout error: {e}")
        return False, "Request timeout"
    except Exception as e:
        print(f"DEBUG - Unexpected error: {e}")
        return False, str(e)


def update_record(record_id, record):
    """Kayıt güncelle"""
    try:
        response = requests.patch(
            f"{POCKETBASE_URL}/api/collections/{COLLECTION_NAME}/records/{record_id}",
            json=record,
            headers=get_headers(),
            timeout=10
        )

        if response.status_code == 200:
            return True, response.json()
        else:
            error_msg = response.text
            try:
                error_data = response.json()
                error_msg = error_data.get('message', error_msg)
            except:
                pass
            return False, error_msg

    except requests.exceptions.ConnectionError:
        return False, f"Cannot connect to PocketBase at {POCKETBASE_URL}"
    except requests.exceptions.Timeout:
        return False, "Request timeout"
    except Exception as e:
        return False, str(e)


def delete_record(record_id):
    """Kayıt sil"""
    try:
        response = requests.delete(
            f"{POCKETBASE_URL}/api/collections/{COLLECTION_NAME}/records/{record_id}",
            headers=get_headers(),
            timeout=10
        )

        if response.status_code == 204:  # PocketBase delete success code
            return True, "Record deleted successfully"
        else:
            error_msg = response.text
            try:
                error_data = response.json()
                error_msg = error_data.get('message', error_msg)
            except:
                pass
            return False, error_msg

    except requests.exceptions.ConnectionError:
        return False, f"Cannot connect to PocketBase at {POCKETBASE_URL}"
    except requests.exceptions.Timeout:
        return False, "Request timeout"
    except Exception as e:
        return False, str(e)


def check_record_exists(amazon_orderid):
    """Kayıt var mı kontrol et - UPDATED: amazon_orderid field'ını kullan"""
    try:
        response = requests.get(
            f"{POCKETBASE_URL}/api/collections/{COLLECTION_NAME}/records",
            params={"filter": f'amazon_orderid="{amazon_orderid}"'},
            headers=get_headers(),
            timeout=10
        )

        if response.status_code == 200:
            items = response.json().get("items", [])
            return len(items) > 0, items[0] if items else None
        else:
            return False, None

    except Exception:
        return False, None


def get_max_master_no():
    """En büyük master_no'yu al"""
    try:
        response = requests.get(
            f"{POCKETBASE_URL}/api/collections/{COLLECTION_NAME}/records",
            params={"sort": "-master_no", "perPage": 1},
            headers=get_headers(),
            timeout=10
        )

        if response.status_code == 200:
            items = response.json().get("items", [])
            if items and "master_no" in items[0]:
                return int(items[0]["master_no"])
        return 0

    except Exception:
        return 0


def get_record_count():
    """Toplam kayıt sayısını al"""
    try:
        response = requests.get(
            f"{POCKETBASE_URL}/api/collections/{COLLECTION_NAME}/records",
            params={"perPage": 1},
            headers=get_headers(),
            timeout=5
        )

        if response.status_code == 200:
            return response.json().get("totalItems", 0)
        return 0

    except Exception:
        return 0


def test_pocketbase_connection():
    """PocketBase bağlantısını test et"""
    try:
        # Basit health check
        response = requests.get(
            f"{POCKETBASE_URL}/api/health",
            timeout=5
        )

        if response.status_code == 200:
            # Collection'ı kontrol et
            collection_response = requests.get(
                f"{POCKETBASE_URL}/api/collections/{COLLECTION_NAME}/records",
                params={"perPage": 1},
                headers=get_headers(),
                timeout=5
            )

            if collection_response.status_code == 200:
                record_count = collection_response.json().get("totalItems", 0)
                return True, f"PocketBase is accessible and '{COLLECTION_NAME}' collection contains {record_count} records"
            elif collection_response.status_code == 401:
                return False, "Authentication failed - Invalid token"
            elif collection_response.status_code == 403:
                return False, "Access denied - Insufficient permissions"
            elif collection_response.status_code == 404:
                return False, f"Collection '{COLLECTION_NAME}' not found"
            else:
                return False, f"Collection access failed: HTTP {collection_response.status_code}"
        else:
            return False, f"PocketBase health check failed: HTTP {response.status_code}"

    except requests.exceptions.ConnectionError:
        return False, f"Cannot connect to PocketBase at {POCKETBASE_URL}"
    except requests.exceptions.Timeout:
        return False, "Connection timeout"
    except Exception as e:
        return False, f"Unexpected error: {str(e)}"


def bulk_upload_records(records, progress_callback=None):
    """Toplu kayıt yükleme - UPDATED: Doğru field adları ile"""
    results = {
        "added": 0,
        "updated": 0,
        "errors": 0,
        "error_details": []
    }

    total_records = len(records)

    for i, record in enumerate(records, 1):
        if progress_callback:
            # UPDATED: amazon_orderid field'ını kullan
            progress_callback(i, total_records, record.get('amazon_orderid', 'N/A'))

        try:
            # UPDATED: JSON'daki gerçek field adını kullan
            amazon_orderid = record.get("amazon_orderid")
            if not amazon_orderid:
                results["errors"] += 1
                results["error_details"].append(f"Record {i}: Missing amazon_orderid")
                continue

            # Kayıt var mı kontrol et
            exists, existing_record = check_record_exists(amazon_orderid)

            if exists:
                # Güncelle
                update_data = record.copy()
                update_data.pop("master_no", None)  # master_no'yu güncelleme sırasında kaldır
                success, response = update_record(existing_record['id'], update_data)

                if success:
                    results["updated"] += 1
                else:
                    results["errors"] += 1
                    results["error_details"].append(f"Update error for {amazon_orderid}: {response}")
            else:
                # Yeni kayıt ekle
                success, response = upload_record(record)

                if success:
                    results["added"] += 1
                else:
                    results["errors"] += 1
                    results["error_details"].append(f"Add error for {amazon_orderid}: {response}")

        except Exception as e:
            results["errors"] += 1
            results["error_details"].append(f"Record {i} processing error: {str(e)}")

    return results


def get_unique_field_for_matching():
    """Matching için kullanılacak unique field'ı döndür"""
    return "amazon_orderid"


def validate_record_fields(record):
    """Kayıt field'larını validate et"""
    required_fields = [
        "master_no",
        "amazon_orderid",  # UPDATED: Doğru field adı
        "ebay_order_number"
    ]

    missing_fields = []
    for field in required_fields:
        if field not in record or not record[field]:
            missing_fields.append(field)

    if missing_fields:
        return False, f"Missing required fields: {', '.join(missing_fields)}"

    return True, "Valid"


def clean_record_for_upload(record):
    """Upload için kaydı temizle"""
    # PocketBase otomatik field'larını kaldır
    cleaned_record = record.copy()

    # PocketBase sistem field'larını kaldır
    system_fields = ['id', 'created', 'updated', 'collectionId', 'collectionName']
    for field in system_fields:
        cleaned_record.pop(field, None)

    return cleaned_record


def test_single_record_upload():
    """Tek kayıt ile test yapma fonksiyonu"""
    test_record = {
        "master_no": 999,
        "ebay_order_creation_date": "Jun 1, 2025",
        "ebay_order_number": "TEST-123",
        "ebay_item_id": "TEST-ITEM-123",
        "ebay_item_title": "Test Product",
        "ebay_buyer_name": "Test User",
        "ebay_ship_to_city": "Test City",
        "ebay_ship_to_province_region_state": "CA",
        "ebay_ship_to_zip": "12345",
        "ebay_ship_to_country": "US",
        "ebay_refunds": None,
        "amazon_orderid": "TEST-AMAZON-123",
        "amazon_orderdate": "2025-06-02",
        "amazon_deliverystatus": "Delivered",
        "amazon_product_title": "Test Amazon Product",
        "amazon_product_url": "https://www.amazon.com/dp/B123456789",
        "amazon_asin": "B123456789",
        "amazon_ship_to": "Test User\n123 Test St, Test City, CA 12345, United States",
        "calculated_ebay_earning_usd": 10.00,
        "calculated_amazon_cost_usd": 8.00,
        "calculated_profit_usd": 2.00,
        "calculated_margin_percent": 20.00,
        "calculated_roi_percent": 25.00,
        "exchange_rate_used": 35.00
    }

    print("DEBUG - Testing single record upload...")
    success, response = upload_record(test_record)

    if success:
        print("DEBUG - Single record upload SUCCESS!")
        return True
    else:
        print(f"DEBUG - Single record upload FAILED: {response}")
        return False


def get_collection_schema():
    """Collection schema'sını al"""
    try:
        response = requests.get(
            f"{POCKETBASE_URL}/api/collections/{COLLECTION_NAME}",
            headers=get_headers(),
            timeout=10
        )

        if response.status_code == 200:
            schema = response.json()
            print(f"DEBUG - Collection schema: {schema}")
            return schema
        else:
            print(f"DEBUG - Could not get schema, status: {response.status_code}")
            return None

    except Exception as e:
        print(f"DEBUG - Schema fetch error: {e}")
        return None