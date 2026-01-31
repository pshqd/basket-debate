<template>
  <div id="app">
    <header class="header">
      <h1>🛒 Мультиагентный Шоппер</h1>
      <p>ИИ за 2 секунды найдёт лучшую корзину</p>
    </header>

    <div class="container">
      
      <aside class="sidebar">
        <h2>Ваш запрос</h2>

        <!-- Поле для ввода запроса на естественном языке -->
        <div class="form-group">
          <label>Что вам нужно?</label>
          <input 
            v-model="userQuery"
            placeholder="ужин на двоих за 1500 без молока"
            @keyup.enter="optimizeBasket"
            class="input"
          />
        </div>

        <button 
          @click="optimizeBasket" 
          :disabled="loading" 
          class="btn-primary"
        >
          {{ loading ? '⏳ Думаю...' : '🚀 Оптимизировать' }}
        </button>

        <hr class="divider">

        <!-- Дополнительные параметры (пока не используются LLM, но можно оставить для будущего) -->
        <h3>Параметры</h3>

        <div class="form-group">
          <label>Диета:</label>
          <select v-model="diet" class="input">
            <option>любая</option>
            <option>веган</option>
            <option>вегетарианец</option>
            <option>кето</option>
          </select>
        </div>

        <div class="form-group">
          <label>Аллергии:</label>
          <input 
            v-model="allergies"
            placeholder="молоко, орехи"
            class="input"
          />
        </div>
      </aside>

      <!-- ========== ПРАВАЯ ПАНЕЛЬ (РЕЗУЛЬТАТЫ) ========== -->
      <main class="content">
        
        <!-- ========== СОСТОЯНИЕ 1: ЗАГРУЗКА ========== -->
        <div v-if="loading" class="state-loading">
          <div class="spinner"></div>
          <p class="loading-text">🤖 Три агента обсуждают вашу корзину...</p>
          <p class="loading-desc">
            🧠 LLM парсит ваш запрос<br>
            💰 Budget Agent ищет дешевле<br>
            🔗 Compatibility Agent проверяет совместимость<br>
            👤 Profile Agent учитывает ваши предпочтения
          </p>
        </div>

        <!-- ========== СОСТОЯНИЕ 2: ОШИБКА ========== -->
        <div v-else-if="error" class="state-error">
          <p class="error-text">{{ error }}</p>
        </div>

        <!-- ========== СОСТОЯНИЕ 3: УСПЕХ (РЕЗУЛЬТАТ) ========== -->
        <div v-else-if="basket.length > 0" class="state-success">
          
          <!-- ========== БЛОК "ЧТО ПОНЯЛ LLM" ========== -->
          <div v-if="parsedConstraints" class="parsed-info">
            <h3>🧠 Что я понял:</h3>
            <div class="parsed-grid">
              
              <!-- Бюджет -->
              <div v-if="parsedConstraints.budget_rub" class="parsed-item">
                <span class="parsed-label">Бюджет:</span>
                <strong>{{ formatPrice(parsedConstraints.budget_rub) }} ₽</strong>
              </div>
              
              <!-- Количество людей -->
              <div v-if="parsedConstraints.people" class="parsed-item">
                <span class="parsed-label">Людей:</span>
                <strong>{{ parsedConstraints.people }}</strong>
              </div>
              
              <!-- Тип приёма пищи -->
              <div v-if="parsedConstraints.meal_type.length > 0" class="parsed-item">
                <span class="parsed-label">Приём пищи:</span>
                <strong>{{ parsedConstraints.meal_type.join(', ') }}</strong>
              </div>
              
              <!-- Запрещённые теги -->
              <div v-if="parsedConstraints.exclude_tags.length > 0" class="parsed-item">
                <span class="parsed-label">Исключить:</span>
                <strong class="exclude">{{ parsedConstraints.exclude_tags.join(', ') }}</strong>
              </div>
              
              <!-- Обязательные теги -->
              <div v-if="parsedConstraints.include_tags.length > 0" class="parsed-item">
                <span class="parsed-label">Обязательно:</span>
                <strong class="include">{{ parsedConstraints.include_tags.join(', ') }}</strong>
              </div>
              
            </div>
          </div>

          <!-- ========== ЗАГОЛОВОК КОРЗИНЫ ========== -->
          <h2>✅ Оптимальная корзина</h2>

          <!-- ========== СПИСОК ТОВАРОВ ========== -->
          <div class="products">
            <div 
              v-for="item in basket"
              :key="item.id"
              class="product-card"
            >
              <!-- Верх карточки: название + бейдж агента -->
              <div class="product-top">
                <h3>{{ item.name }}</h3>
                <span class="badge" :class="'badge-' + item.agent">
                  {{ agentLabel[item.agent] }}
                </span>
              </div>
              
              <!-- Причина выбора товара -->
              <p class="product-reason">{{ item.reason }}</p>
              
              <!-- Низ карточки: цена + рейтинг -->
              <div class="product-bottom">
                <span class="price">{{ formatPrice(item.price) }} ₽</span>
                <span class="rating">⭐ {{ item.rating || 4.5 }}</span>
              </div>
            </div>
          </div>

          <!-- ========== ИТОГОВАЯ СВОДКА ========== -->
          <div class="summary">
            <div class="summary-row">
              <span>Товаров:</span>
              <strong>{{ basket.length }}</strong>
            </div>
            <div class="summary-row">
              <span>Сумма:</span>
              <strong class="price">{{ formatPrice(totalPrice) }} ₽</strong>
            </div>
            <div class="summary-row">
              <span>Экономия:</span>
              <strong class="savings">-{{ formatPrice(originalPrice - totalPrice) }} ₽</strong>
            </div>
          </div>

          <!-- ========== КНОПКА "ДОБАВИТЬ В КОРЗИНУ" ========== -->
          <button @click="addToCart" class="btn-secondary">
            🛍️ Добавить в корзину
          </button>
        </div>

        <!-- ========== СОСТОЯНИЕ 4: ПУСТО (НАЧАЛЬНОЕ) ========== -->
        <div v-else class="state-empty">
          <p class="empty-text">📋 Введите запрос и нажмите кнопку</p>
        </div>

      </main>
    </div>
  </div>
</template>

<script setup>
import { useBasket } from './composables/useBasket'
import './App.css'

// Импортируем всё из composable (reactive state + методы)
const {
  userQuery,          // ref: текст запроса пользователя
  basket,             // ref: массив товаров в корзине
  loading,            // ref: флаг загрузки
  error,              // ref: текст ошибки
  diet,               // ref: выбранная диета
  allergies,          // ref: аллергии
  originalPrice,      // ref: исходная цена (до скидки)
  totalPrice,         // computed: сумма всех товаров
  agentLabel,         // object: маппинг agent -> название
  parsedConstraints,  // ref: результат LLM-парсинга
  optimizeBasket,     // function: запуск оптимизации
  formatPrice,        // function: форматирование цены
  addToCart           // function: добавление в корзину
} = useBasket()
</script>
