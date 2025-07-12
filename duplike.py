import json
from collections import Counter

# Matched dosyasını oku
with open("/Users/eylullonner/Downloads/matched_orders_multi_account_20250705_132843.json", "r") as f:
    matched_orders = json.load(f)

# amazon_orderid'leri topla
order_ids = [order["amazon_orderid"] for order in matched_orders]

# Kaç kere geçtiğini say
counts = Counter(order_ids)

# Birden fazla geçenleri filtrele
duplicates = [order_id for order_id, count in counts.items() if count > 1]

# Sonuçları yazdır
print("🔁 Duplicate Amazon Order ID'ler:")
for order_id in duplicates:
    print(f"- {order_id} (x{counts[order_id]})")

print(f"\nToplam duplicate sayısı: {len(duplicates)}")
