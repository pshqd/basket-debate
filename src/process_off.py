import pandas as pd
import sqlite3
from pathlib import Path
from tqdm import tqdm
import logging

logging.basicConfig(level=logging.INFO)

def create_schema(db_path: Path):
    """Создаёт схему БД под NLP/агенты."""
    conn = sqlite3.connect(db_path)
    
    conn.execute("""
        CREATE TABLE IF NOT EXISTS products (
            code TEXT PRIMARY KEY,
            name TEXT,
            brands TEXT,
            category TEXT,
            price_rub REAL,
            ingredients_text TEXT,
            allergens_tags TEXT,
            countries_tags TEXT,
            tags TEXT,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Индексы для скорости NLP-фильтров
    conn.execute("CREATE INDEX IF NOT EXISTS idx_tags ON products(tags)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_category ON products(category)")
    
    conn.commit()
    conn.close()

def normalize_tags(ingredients_text, allergens_tags):
    """Извлекает теги для NLP: dairy, gluten, vegan."""
    tags = set()
    
    # Из аллергенов
    if pd.notna(allergens_tags):
        allg = allergens_tags.lower()
        if 'milk' in allg or 'lactose' in allg:
            tags.add('dairy')
        if 'gluten' in allg or 'wheat' in allg:
            tags.add('gluten')
    
    # Из ингредиентов (ключевые слова)
    if pd.notna(ingredients_text):
        text = ingredients_text.lower()
        if any(w in text for w in ['молоко', 'сыр', 'творог', 'кефир', 'сливки']):
            tags.add('dairy')
        if any(w in text for w in ['пшеница', 'пшеничная мука']):
            tags.add('gluten')
        if 'сахар' not in text:
            tags.add('sugar_free')  # упрощённо
    
    return ','.join(tags) if tags else None

def process_chunk(chunk, db_path):
    """Обрабатывает один чанк → SQLite."""
    # Фильтр: Россия + полные данные
    ru_mask = chunk['countries_tags'].str.contains('ru|russia|en:russia', case=False, na=False)
    name_mask = chunk['product_name'].notna() & (chunk['product_name'].str.len() > 2)
    
    chunk = chunk[ru_mask & name_mask].copy()
    
    if chunk.empty:
        return 0
    
    # Нормализация
    chunk['category'] = chunk['categories_tags'].str.split(',').str[0].str.strip()
    chunk['price_rub'] = 200.0  # Пока примерная цена
    chunk['tags'] = chunk.apply(
        lambda row: normalize_tags(row.get('ingredients_text'), row.get('allergens_tags')), 
        axis=1
    )
    
    # Выбираем поля
    cols = ['code', 'product_name', 'brands', 'category', 'price_rub', 
            'ingredients_text', 'allergens_tags', 'countries_tags', 'tags']
    clean_chunk = chunk[cols].dropna(subset=['code'])
    
    # В SQLite
    conn = sqlite3.connect(db_path)
    clean_chunk.to_sql('products', conn, if_exists='append', index=False)
    conn.close()
    
    return len(clean_chunk)

def main():
    raw_path = Path('raw/en.openfoodfacts.org.products.csv')
    db_path = Path('processed/products.db')
    
    db_path.parent.mkdir(exist_ok=True)
    create_schema(db_path)
    
    total = 0
    usecols = ['code', 'product_name', 'brands', 'categories_tags', 'countries_tags', 
               'ingredients_text', 'allergens_tags']
    
    with tqdm(desc="Processing chunks") as pbar:
        for chunk in pd.read_csv(
            raw_path, sep='\t', compression='gzip', 
            usecols=lambda c: c in usecols,
            chunksize=100_000,
            low_memory=False,
            encoding_errors='replace'
        ):
            n = process_chunk(chunk, db_path)
            total += n
            pbar.update(1)
            pbar.set_postfix({'products': total})
    
    logging.info(f"Загружено {total} товаров в {db_path}")

if __name__ == "__main__":
    main()
