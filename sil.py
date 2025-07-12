


import json

# Dosyaları oku
with open("/Users/eylullonner/Desktop/buyer-7_orders_52.json", "r") as f:
    original_orders = json.load(f)

with open("/Users/eylullonner/Downloads/matched_orders_multi_account_20250705_132843.json", "r") as f:
    matched_orders = json.load(f)

# matched dosyasındaki amazon_orderid'leri topla
matched_ids = set(order["amazon_orderid"] for order in matched_orders)

# original dosyasında olup matched'de olmayanları bul
missing_orders = [order for order in original_orders if order["orderId"] not in matched_ids]

# Eksikleri yazdır
print("❗️ Missing Amazon Orders (Not Matched):")
for order in missing_orders:
    print(f"- {order['orderId']}")

print(f"\nToplam eksik sipariş sayısı: {len(missing_orders)}")

