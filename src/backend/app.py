# src/backend/app.py
"""
Flask API для генерации корзин.
"""

from flask import Flask, jsonify, request
from flask_cors import CORS
import os
import sys
from pathlib import Path
from dotenv import load_dotenv
from src.utils.database import init_db_for_flask, get_db, get_db_stats
import logging

# Добавляем корень проекта в PYTHONPATH
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.backend.agent_pipeline import AgentPipeline

load_dotenv()
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

pipeline = None


def create_app():
    """
    Application Factory для Flask.
    Создаёт и настраивает Flask-приложение.
    """
    global pipeline
    
    app = Flask(__name__)
    
    # CORS
    CORS(app, resources={
        r"/*": {
            "origins": ["http://localhost:5173", "http://127.0.0.1:5173"],
            "methods": ["GET", "POST", "OPTIONS"],
            "allow_headers": ["Content-Type"]
        }
    })
    
    # Секретный ключ
    app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'dev-secret-key')
    init_db_for_flask(app)
    logger.info("✅ Database integration активирована")

    # Инициализируем пайплайн при старте (только один раз)
    if pipeline is None:
        logger.info("🚀 Инициализация пайплайна...")
        pipeline = AgentPipeline()
        logger.info("✅ Пайплайн готов")
    
    
    @app.route('/')
    def index():
        """Главная страница."""
        return jsonify({
            "message": "🛒 Basket Debate API",
            "version": "1.0.0",
            "endpoints": {
                "health": "/health",
                "generate_basket": "/api/generate-basket (POST)",
                "products": "/api/products (GET)",
                "stats": "/api/stats (GET)"
            }
        })
    
    
    @app.route('/health')
    def health():
        """Health check."""
        return jsonify({
            "status": "ok",
            "service": "basket-debate-api",
            "pipeline_ready": pipeline is not None
        })
    
    
    @app.route('/api/generate-basket', methods=['POST'])
    def generate_basket():
        """
        Генерация корзины через агентов.
        
        POST /api/generate-basket
        Body:
        {
            "query": "ужин на троих за 2000 без молока"
        }
        """
        try:
            data = request.get_json()
            
            if not data:
                return jsonify({
                    "status": "error",
                    "message": "Request body is required"
                }), 400
            
            user_query = data.get('query', '')
            
            if not user_query:
                return jsonify({
                    "status": "error",
                    "message": "Field 'query' is required"
                }), 400
            
            logger.info(f"\n{'='*70}")
            logger.info(f"📥 Новый запрос: {user_query}")
            logger.info(f"{'='*70}")
            
            # Запускаем пайплайн
            result = pipeline.process(user_query)
            exec_time = result.get('summary', {}).get('execution_time_sec', 0)

            logger.info(f"\n✅ Обработано за {exec_time}")
            logger.info(f"{'='*70}\n")
            
            return jsonify(result)
        
        except Exception as e:
            import traceback
            logger.exception("❌ Ошибка в /api/generate-basket")
            traceback.print_exc()
            
            return jsonify({
                "status": "error",
                "message": str(e),
                "type": type(e).__name__
            }), 500
    
    @app.route('/api/products', methods=['GET'])
    def get_products():
        """
        Получить список товаров с фильтрами.
        
        Query params:
            - category: фильтр по категории (опционально)
            - max_price: максимальная цена (опционально)
            - limit: количество товаров (default 20)
        
        Пример:
            GET /api/products?category=Молоко&max_price=100&limit=10
        """
        try:
            db = get_db()
            cursor = db.cursor()
            
            # Параметры из query string
            category = request.args.get('category')
            max_price = request.args.get('max_price', type=float)
            limit = request.args.get('limit', default=20, type=int)
            
            # Строим SQL
            query = "SELECT id, product_name, price_per_unit, unit, product_category FROM products WHERE 1=1"
            params = []
            
            if category:
                query += " AND product_category LIKE ?"
                params.append(f"%{category}%")
            
            if max_price:
                query += " AND price_per_unit <= ?"
                params.append(max_price)
            
            query += " LIMIT ?"
            params.append(limit)
            
            cursor.execute(query, params)
            products = [dict(row) for row in cursor.fetchall()]
            
            logger.info(f"📦 Отправлено {len(products)} товаров")
            
            return jsonify({
                'status': 'success',
                'products': products,
                'count': len(products)
            }), 200
        
        except Exception as e:
            logger.exception("❌ Ошибка в /api/products")
            return jsonify({
                'status': 'error',
                'message': str(e)
            }), 500
    @app.route('/api/stats', methods=['GET'])
    def get_stats():
        """
        Статистика по БД.
        
        Response:
            {
                "status": "success",
                "stats": {
                    "total_products": 10000,
                    "products_with_embeddings": 9500,
                    "avg_price": 145.67,
                    "categories_count": 25
                }
            }
        """
        try:
            stats = get_db_stats()
            
            logger.info("📊 Статистика БД отправлена")
            
            return jsonify({
                'status': 'success',
                'stats': stats
            }), 200
        
        except Exception as e:
            logger.exception("❌ Ошибка в /api/stats")
            return jsonify({
                'status': 'error',
                'message': str(e)
            }), 500

    return app

if __name__ == '__main__':
    logger.info(f"📂 Project root: {PROJECT_ROOT}")
    logger.info(f"🐍 Python path: {sys.path[:3]}")
    
    app = create_app()
    
    logger.info("🚀 Запуск Flask сервера на http://0.0.0.0:5000")
    app.run(debug=True, host='0.0.0.0', port=5000)

