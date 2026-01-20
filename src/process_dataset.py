import pandas as pd
import sqlite3
from pathlib import Path
from tqdm import tqdm
import re
import math
import json

JSON_PATH =  Path("data/tag_rules.json") 
INPUT_FILE = Path("data/raw/russian_supermarket_prices.csv")      
DB_PATH = Path("data/processed/products.db")      

with open(JSON_PATH, "r", encoding="utf-8") as f:
    TAG_RULES = json.load(f)
    

USECOLS = ['product_name', 'product_category', 'brand',
       'package_size', 'unit','new_price']

DB_SCHEMA = {
    "product_name": "TEXT",
    "product_category": "TEXT",
    "brand": "TEXT",
    "package_size": "REAL",
    "unit": "TEXT",
    "price_per_unit": "REAL",
    "tags": "TEXT"
}

def to_float(x):
    try:
        return float(str(x).replace(',', '.'))
    except Exception:
        return math.nan

def create_db_schema():
    """Создаёт таблицы с ТВОЕЙ схемой."""
    conn = sqlite3.connect(DB_PATH)
    conn.execute("DROP TABLE IF EXISTS products")
    columns_sql = ", ".join([f"{k} {v}" for k, v in DB_SCHEMA.items()])
    conn.execute(f"""
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            {columns_sql}
        )
    """)
    conn.commit()
    conn.close()

def normalize_price(price, size, unit):
    """
    Возвращает цену за:
    - 1 кг
    - 1 л
    - 1 шт
    """
    if not unit:
        return int(price / size * 1000)
    
    if math.isnan(size):
        return math.nan

    unit = str(unit).lower()

    if unit == 'г':
        return round(price / size * 1000, 2)
    if unit == 'мл':
        return round(price / size * 1000, 2)
    if unit == 'л':
        return round(price / size, 2)
    if unit == 'шт':
        return round(price / size, 2)

    return math.nan


def clean_product_name(name):
    pattern = r'\s*\d+[.,]?\d*\s*(?:г|мл|л|кг|шт|уп|упаковка|пачка|бут|банка)\b.*'
    cleaned = re.sub(pattern, '', str(name), flags=re.IGNORECASE).strip()
    return cleaned

def extract_tags(product_name, product_category):
    name = str(product_name).lower()
    category = str(product_category).lower()

    tags = set()

    for tag, rules in TAG_RULES.items():
        for field, keywords in rules.items():
            text = name if field == "name" else category

            if any(word in text for word in keywords):
                tags.add(tag)

    return sorted(tags)


def normalize_row(row):
    name = clean_product_name(row['product_name'])

    size = to_float(row['package_size'])
    unit = row['unit']
    price = row['new_price']

    price_per_unit = normalize_price(price, size, unit)

    tags = extract_tags(
        product_name=name,
        product_category=row['product_category']
    )
    return {
        "product_name": name,
        "product_category": row['product_category'],
        "brand": row['brand'],
        "package_size": size,
        "unit": unit,
        "price_per_unit": price_per_unit,
        "tags": "|".join(tags)
    }

def process_chunk(chunk):
    chunk = chunk.dropna(subset=['product_name', 'new_price'])
    rows = []

    for _, row in chunk.iterrows():
        rows.append(normalize_row(row))

    return pd.DataFrame(rows)

def main():
    DB_PATH.parent.mkdir(exist_ok=True)
    create_db_schema()
    
    total = 0
    chunksize = 50_000  
    
    conn = sqlite3.connect(DB_PATH)
    
    for chunk_num, chunk in enumerate(
        pd.read_csv(INPUT_FILE, usecols=USECOLS, chunksize=chunksize)
    ):
        print(f"Чанк {chunk_num}: {len(chunk)} строк")
        
        processed = process_chunk(chunk)
        if not processed.empty:
            processed.to_sql('products', conn, if_exists='append', index=False)
            total += len(processed)
    
    conn.close()
    print(f"Загружено {total} товаров!")

if __name__ == "__main__":
    main()
