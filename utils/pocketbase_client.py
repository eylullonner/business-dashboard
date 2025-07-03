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


def check_record_exists(amazon_orderid, amazon_account=None):
    """
    Kayıt var mı kontrol et - UPDATED: Composite key (orderid + account)

    Args:
        amazon_orderid (str): Amazon order ID
        amazon_account (str, optional): Amazon account name

    Returns:
        tuple: (exists: bool, existing_record: dict or None)
    """
    try:
        # Composite key approach - both orderid and account must match
        if amazon_account:
            filter_query = f'amazon_orderid="{amazon_orderid}" && amazon_account="{amazon_account}"'
            print(f"DEBUG - Composite key search: orderid={amazon_orderid}, account={amazon_account}")
        else:
            # Fallback - only orderid (for backward compatibility)
            filter_query = f'amazon_orderid="{amazon_orderid}"'
            print(f"DEBUG - Single key search: orderid={amazon_orderid}")

        response = requests.get(
            f"{POCKETBASE_URL}/api/collections/{COLLECTION_NAME}/records",
            params={"filter": filter_query},
            headers=get_headers(),
            timeout=10
        )

        print(f"DEBUG - Filter query: {filter_query}")
        print(f"DEBUG - Search response status: {response.status_code}")

        if response.status_code == 200:
            items = response.json().get("items", [])
            print(f"DEBUG - Found {len(items)} existing records")

            if items:
                existing_record = items[0]
                print(f"DEBUG - Existing record ID: {existing_record.get('id', 'N/A')}")
                return True, existing_record
            else:
                print("DEBUG - No existing records found")
                return False, None
        else:
            print(f"DEBUG - Search failed with status: {response.status_code}")
            return False, None

    except Exception as e:
        print(f"DEBUG - Exception in check_record_exists: {e}")
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
    """PocketBase bağlantısını test et - amazon_account field kontrolü dahil"""
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

                # amazon_account field'ının varlığını kontrol et
                if record_count > 0:
                    # Sample record al ve amazon_account field'ını kontrol et
                    sample_record = collection_response.json().get("items", [])
                    if sample_record:
                        has_account_field = 'amazon_account' in sample_record[0]
                        if has_account_field:
                            return True, f"PocketBase is accessible, '{COLLECTION_NAME}' collection contains {record_count} records with amazon_account field ✅"
                        else:
                            return True, f"PocketBase is accessible, '{COLLECTION_NAME}' collection contains {record_count} records ⚠️ amazon_account field missing!"
                    else:
                        return True, f"PocketBase is accessible and '{COLLECTION_NAME}' collection contains {record_count} records"
                else:
                    return True, f"PocketBase is accessible and '{COLLECTION_NAME}' collection is empty (amazon_account field status unknown)"

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
    """
    Toplu kayıt yükleme - UPDATED: Composite key (amazon_orderid + amazon_account)

    Args:
        records (list): Upload edilecek kayıtlar
        progress_callback (function, optional): Progress callback fonksiyonu

    Returns:
        dict: Upload sonuçları (added, updated, errors)
    """
    results = {
        "added": 0,
        "updated": 0,
        "errors": 0,
        "error_details": []
    }

    total_records = len(records)
    print(f"DEBUG - Starting bulk upload of {total_records} records")

    for i, record in enumerate(records, 1):
        if progress_callback:
            # Progress callback için amazon_orderid kullan
            progress_callback(i, total_records, record.get('amazon_orderid', 'N/A'))

        try:
            # UPDATED: Composite key extraction
            amazon_orderid = record.get("amazon_orderid")
            amazon_account = record.get("amazon_account")

            print(f"DEBUG - Processing record {i}: orderid={amazon_orderid}, account={amazon_account}")

            if not amazon_orderid:
                results["errors"] += 1
                results["error_details"].append(f"Record {i}: Missing amazon_orderid")
                print(f"DEBUG - Record {i}: Missing amazon_orderid")
                continue

            # Enhanced existence check with composite key
            exists, existing_record = check_record_exists(amazon_orderid, amazon_account)

            if exists:
                print(f"DEBUG - Record exists, updating: {amazon_orderid} ({amazon_account})")
                # Güncelle
                update_data = record.copy()
                update_data.pop("master_no", None)  # master_no'yu güncelleme sırasında kaldır
                success, response = update_record(existing_record['id'], update_data)

                if success:
                    results["updated"] += 1
                    print(f"DEBUG - Update successful for {amazon_orderid}")
                else:
                    results["errors"] += 1
                    error_msg = f"Update error for {amazon_orderid} ({amazon_account}): {response}"
                    results["error_details"].append(error_msg)
                    print(f"DEBUG - Update failed: {error_msg}")
            else:
                print(f"DEBUG - New record, adding: {amazon_orderid} ({amazon_account})")
                # Yeni kayıt ekle
                success, response = upload_record(record)

                if success:
                    results["added"] += 1
                    print(f"DEBUG - Add successful for {amazon_orderid}")
                else:
                    results["errors"] += 1
                    error_msg = f"Add error for {amazon_orderid} ({amazon_account}): {response}"
                    results["error_details"].append(error_msg)
                    print(f"DEBUG - Add failed: {error_msg}")

        except Exception as e:
            results["errors"] += 1
            error_msg = f"Record {i} processing error: {str(e)}"
            results["error_details"].append(error_msg)
            print(f"DEBUG - Processing exception: {error_msg}")

    print(f"DEBUG - Bulk upload completed: {results}")
    return results


def get_unique_field_for_matching():
    """Matching için kullanılacak unique field'ları döndür - UPDATED: Composite key"""
    return ["amazon_orderid", "amazon_account"]


def validate_record_fields(record):
    """Kayıt field'larını validate et - UPDATED: amazon_account field dahil"""
    required_fields = [
        "master_no",
        "amazon_orderid",
        "amazon_account",  # YENİ ZORUNLU FIELD
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
    """Tek kayıt ile test yapma fonksiyonu - UPDATED: amazon_account field dahil"""
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
        "amazon_account": "test_account",  # YENİ FIELD
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

    print("DEBUG - Testing single record upload with amazon_account field...")
    success, response = upload_record(test_record)

    if success:
        print("DEBUG - Single record upload SUCCESS!")

        # Test existence check with composite key
        print("DEBUG - Testing composite key existence check...")
        exists, existing_record = check_record_exists("TEST-AMAZON-123", "test_account")

        if exists:
            print("DEBUG - Composite key check SUCCESS!")
            return True
        else:
            print("DEBUG - Composite key check FAILED!")
            return False
    else:
        print(f"DEBUG - Single record upload FAILED: {response}")
        return False


def get_collection_schema():
    """Collection schema'sını al - amazon_account field kontrolü dahil"""
    try:
        response = requests.get(
            f"{POCKETBASE_URL}/api/collections/{COLLECTION_NAME}",
            headers=get_headers(),
            timeout=10
        )

        if response.status_code == 200:
            schema = response.json()
            print(f"DEBUG - Collection schema: {schema}")

            # amazon_account field'ının varlığını kontrol et
            schema_fields = schema.get('schema', [])
            has_amazon_account = any(field.get('name') == 'amazon_account' for field in schema_fields)

            if has_amazon_account:
                print("DEBUG - amazon_account field found in schema ✅")
            else:
                print("DEBUG - amazon_account field NOT found in schema ❌")

            return schema
        else:
            print(f"DEBUG - Could not get schema, status: {response.status_code}")
            return None

    except Exception as e:
        print(f"DEBUG - Schema fetch error: {e}")
        return None


def get_records_by_account(amazon_account, limit=10):
    """Belirli bir Amazon account'a ait kayıtları getir - YENİ FONKSIYON"""
    try:
        response = requests.get(
            f"{POCKETBASE_URL}/api/collections/{COLLECTION_NAME}/records",
            params={
                "filter": f'amazon_account="{amazon_account}"',
                "perPage": limit,
                "sort": "-created"
            },
            headers=get_headers(),
            timeout=10
        )

        if response.status_code == 200:
            return response.json().get("items", [])
        else:
            print(f"DEBUG - get_records_by_account failed: {response.status_code}")
            return []

    except Exception as e:
        print(f"DEBUG - get_records_by_account error: {e}")
        return []


def get_account_summary():
    """Account bazında özet bilgi al - YENİ FONKSIYON"""
    try:
        response = requests.get(
            f"{POCKETBASE_URL}/api/collections/{COLLECTION_NAME}/records",
            params={"perPage": 500},  # Büyük limit - tüm kayıtları almaya çalış
            headers=get_headers(),
            timeout=15
        )

        if response.status_code == 200:
            records = response.json().get("items", [])

            # Account bazında gruplama
            account_summary = {}
            for record in records:
                account = record.get('amazon_account', 'unknown')
                if account not in account_summary:
                    account_summary[account] = {
                        'count': 0,
                        'total_profit': 0,
                        'total_cost': 0
                    }

                account_summary[account]['count'] += 1
                account_summary[account]['total_profit'] += float(record.get('calculated_profit_usd', 0))
                account_summary[account]['total_cost'] += float(record.get('calculated_amazon_cost_usd', 0))

            print(f"DEBUG - Account summary: {account_summary}")
            return account_summary
        else:
            print(f"DEBUG - get_account_summary failed: {response.status_code}")
            return {}

    except Exception as e:
        print(f"DEBUG - get_account_summary error: {e}")
        return {}


def delete_records_by_account(amazon_account):
    """Belirli bir account'ın tüm kayıtlarını sil - YENİ FONKSIYON"""
    try:
        # Önce account'a ait kayıtları bul
        records = get_records_by_account(amazon_account, limit=1000)

        deleted_count = 0
        error_count = 0

        for record in records:
            success, message = delete_record(record['id'])
            if success:
                deleted_count += 1
            else:
                error_count += 1
                print(f"DEBUG - Delete failed for record {record['id']}: {message}")

        print(f"DEBUG - Account deletion summary: {deleted_count} deleted, {error_count} errors")
        return deleted_count, error_count

    except Exception as e:
        print(f"DEBUG - delete_records_by_account error: {e}")
        return 0, 1