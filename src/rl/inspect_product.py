# src/rl/inspect_product.py
"""
Проверяем, что за товар выбирает политика.
"""

from src.backend.db.queries import fetch_candidate_products
from src.agent.utils import pad_products_to_k

constraints = {
    "budget_rub": 1500,
    "exclude_tags": ["dairy"],
    "include_tags": [],
    "meal_type": ["dinner"],
    "people": 3,
}

products = fetch_candidate_products(constraints, limit=100)
products = pad_products_to_k(products, k=100)

# Проверяем товар #65 (action 65 → index 64)
product_idx = 64
product = products[product_idx]

print("=" * 70)
print(f"🔍 Товар, который выбирает политика (action=65, index=64):\n")
print(f"   Название: {product['product_name']}")
print(f"   Категория: {product['product_category']}")
print(f"   Цена: {product['price_per_unit']:.2f}₽/{product['unit']}")
print(f"   Теги: {product['tags']}")
print(f"   ID: {product['id']}")
print("=" * 70)

# Проверяем первые 10 товаров для контекста
print("\n📦 Первые 10 товаров в списке:\n")
for i in range(10):
    p = products[i]
    print(f"   {i:2d}. {p['product_name']:40s} — {p['price_per_unit']:6.2f}₽ [{p['product_category']}]")

print("\n📦 Товары вокруг #65 (60-70):\n")
for i in range(60, 71):
    p = products[i]
    marker = "👉" if i == 64 else "  "
    print(f"   {marker} {i:2d}. {p['product_name']:40s} — {p['price_per_unit']:6.2f}₽")
