# src/scripts/build_embeddings.py
"""
Генерация embeddings для всех товаров в products.db.

Процесс:
1. Загружает модель SentenceTransformer
2. Читает все товары БЕЗ embeddings
3. Генерирует embeddings батчами
4. Обновляет колонку embedding в БД

Запуск:
    # Все товары без embeddings
    uv run python -m src.scripts.build_embeddings
    
    # Пересоздать все embeddings (включая существующие)
    uv run python -m src.scripts.build_embeddings --rebuild
    
    # Только mock товары
    uv run python -m src.scripts.build_embeddings --mocks-only
"""

import argparse
import numpy as np
import torch
from pathlib import Path
from sentence_transformers import SentenceTransformer
from tqdm import tqdm
from typing import List, Tuple

# ==================== ИМПОРТЫ ====================
from src.utils.queries import get_connection, DB_PATH


# ==================== КОНФИГУРАЦИЯ ====================

MODEL_NAME = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
BATCH_SIZE = 512 


# ==================== ФУНКЦИИ ====================

def get_device() -> str:
    """Определяет оптимальное устройство."""
    if torch.backends.mps.is_available():
        return "mps"
    elif torch.cuda.is_available():
        return "cuda"
    else:
        return "cpu"


def load_model(device: str) -> SentenceTransformer:
    """Загружает модель SentenceTransformer."""
    print(f"🔄 Загрузка модели {MODEL_NAME} на {device.upper()}...")
    model = SentenceTransformer(MODEL_NAME, device=device)
    embedding_dim = model.get_sentence_embedding_dimension()
    print(f"   ✅ Модель загружена (размерность: {embedding_dim})")
    return model


def fetch_products_without_embeddings(mocks_only: bool = False) -> List[Tuple]:
    """
    Получает товары без embeddings.
    
    Args:
        mocks_only: Только mock товары (id >= 900000)
    
    Returns:
        List[Tuple]: [(id, product_name, product_category, brand), ...]
    """
    conn = get_connection()
    cursor = conn.cursor()
    
    query = """
        SELECT id, product_name, product_category, brand
        FROM products
        WHERE embedding IS NULL
    """
    
    if mocks_only:
        query += " AND id >= 900000"
    
    query += " ORDER BY id"
    
    cursor.execute(query)
    products = cursor.fetchall()
    conn.close()
    
    # Конвертируем Row в tuple
    return [(row['id'], row['product_name'], row['product_category'], row['brand']) 
            for row in products]


def create_embedding_text(product_name: str, product_category: str, brand: str) -> str:
    """
    Создаёт текст для embedding.
    
    Формат: "Название Категория Бренд"
    """
    name = str(product_name).strip() if product_name else ""
    category = str(product_category).strip() if product_category else ""
    brand_str = str(brand).strip() if brand else ""
    
    text = f"{name} {category} {brand_str}".strip()
    return text


def save_embeddings_batch(product_ids: List[int], embeddings: np.ndarray):
    """Сохраняет батч embeddings в БД."""
    conn = get_connection()
    cursor = conn.cursor()
    
    data = []
    for product_id, embedding in zip(product_ids, embeddings):
        embedding_bytes = embedding.astype(np.float32).tobytes()
        data.append((embedding_bytes, product_id))
    
    cursor.executemany("""
        UPDATE products
        SET embedding = ?
        WHERE id = ?
    """, data)
    
    conn.commit()
    conn.close()


def rebuild_all_embeddings():
    """Удаляет все embeddings для пересоздания."""
    print("\n🗑️  Удаление всех существующих embeddings...")
    
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute("UPDATE products SET embedding = NULL")
    conn.commit()
    
    cursor.execute("SELECT COUNT(*) FROM products")
    total = cursor.fetchone()[0]
    
    conn.close()
    
    print(f"   ✅ Очищено embeddings для {total:,} товаров")


def build_embeddings(mocks_only: bool = False, rebuild: bool = False):
    """
    Главная функция генерации embeddings.
    
    Args:
        mocks_only: Только mock товары
        rebuild: Пересоздать все embeddings
    """
    print("=" * 70)
    print("🧠 ГЕНЕРАЦИЯ EMBEDDINGS")
    print("=" * 70)
    
    # Проверка БД
    if not DB_PATH.exists():
        print(f"❌ БД не найдена: {DB_PATH}")
        print("   Запустите: uv run python -m src.scripts.prepare_db")
        return
    
    # Пересоздание
    if rebuild:
        rebuild_all_embeddings()
    
    # Определяем устройство
    device = get_device()
    print(f"🖥️  Устройство: {device.upper()}")
    
    # Загружаем модель
    model = load_model(device)
    
    # Загружаем товары
    print(f"\n📚 Загрузка товаров...")
    products = fetch_products_without_embeddings(mocks_only=mocks_only)
    
    if not products:
        print("✅ Все товары уже имеют embeddings!")
        return
    
    total = len(products)
    print(f"   Найдено товаров без embeddings: {total:,}")
    
    # Генерация по батчам
    print(f"\n🔄 Генерация embeddings (batch_size={BATCH_SIZE})...")
    
    num_batches = (total + BATCH_SIZE - 1) // BATCH_SIZE
    
    for batch_idx in tqdm(range(num_batches), desc="Батчи"):
        start_idx = batch_idx * BATCH_SIZE
        end_idx = min(start_idx + BATCH_SIZE, total)
        batch_products = products[start_idx:end_idx]
        
        # Формируем тексты
        batch_texts = [
            create_embedding_text(name, category, brand)
            for _, name, category, brand in batch_products
        ]
        
        # Генерируем embeddings
        batch_embeddings = model.encode(
            batch_texts,
            convert_to_numpy=True,
            show_progress_bar=False,
            batch_size=BATCH_SIZE
        )
        
        # Сохраняем
        batch_ids = [product_id for product_id, _, _, _ in batch_products]
        save_embeddings_batch(batch_ids, batch_embeddings)
    
    # Финальная статистика
    print("\n" + "=" * 70)
    print("📊 СТАТИСТИКА")
    print("=" * 70)
    
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT COUNT(*) FROM products WHERE embedding IS NOT NULL")
    with_embeddings = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM products")
    total_products = cursor.fetchone()[0]
    
    conn.close()
    
    embedding_dim = model.get_sentence_embedding_dimension()
    
    print(f"Обработано товаров: {total:,}")
    print(f"Товаров с embeddings: {with_embeddings:,} / {total_products:,}")
    print(f"Размерность: {embedding_dim}")
    print(f"Размер одного embedding: {embedding_dim * 4 / 1024:.2f} KB")
    print(f"Общий размер: {with_embeddings * embedding_dim * 4 / 1024 / 1024:.2f} MB")
    print("=" * 70)
    print("✅ EMBEDDINGS СОЗДАНЫ")
    print("=" * 70)


# ==================== MAIN ====================

def main():
    """CLI интерфейс."""
    parser = argparse.ArgumentParser(description='Генерация embeddings для products.db')
    parser.add_argument(
        '--mocks-only',
        action='store_true',
        help='Генерировать только для mock товаров'
    )
    parser.add_argument(
        '--rebuild',
        action='store_true',
        help='Пересоздать все embeddings (удалить существующие)'
    )
    
    args = parser.parse_args()
    
    build_embeddings(mocks_only=args.mocks_only, rebuild=args.rebuild)


if __name__ == "__main__":
    main()
