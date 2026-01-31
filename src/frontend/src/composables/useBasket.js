// src/frontend/src/composables/useBasket.js
import { ref, computed } from 'vue'

export function useBasket() {
  // === STATE ===
  const userQuery = ref('')
  const basket = ref([])
  const loading = ref(false)
  const error = ref(null)
  const diet = ref('любая')
  const allergies = ref('')
  const originalPrice = ref(0)
  const parsedConstraints = ref(null)  // НОВОЕ: что понял LLM

  // === COMPUTED ===
  const totalPrice = computed(() => 
    basket.value.reduce((sum, item) => sum + (item.price || 0), 0)
  )

  const agentLabel = {
    budget: '💰 Бюджет',
    compatibility: '🔗 Совместимость',
    profile: '👤 Профиль'
  }

  // === METHODS ===
  async function optimizeBasket() {
    if (!userQuery.value.trim()) {
      error.value = '⚠️ Введите запрос!'
      basket.value = []
      parsedConstraints.value = null
      return
    }

    loading.value = true
    error.value = null
    basket.value = []
    parsedConstraints.value = null

    try {
      // ИЗМЕНЕНО: Новый endpoint с LLM-парсингом
      const response = await fetch('http://localhost:5000/api/parse-and-optimize', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          query: userQuery.value
          // diet и allergies пока не используем, LLM сам всё вытащит из текста
        })
      })

      if (!response.ok) {
        throw new Error(`Server error ${response.status}`)
      }

      const data = await response.json()

      if (data.status === 'success') {
        basket.value = data.basket || []
        originalPrice.value = data.summary?.original_price || 0
        parsedConstraints.value = data.parsed  // НОВОЕ: сохраняем то, что понял LLM
      } else {
        throw new Error(data.message || 'Unknown error')
      }

    } catch (err) {
      error.value = `❌ Ошибка: ${err.message}`
      console.error('Optimization error:', err)
    } finally {
      loading.value = false
    }
  }

  function formatPrice(price) {
    return new Intl.NumberFormat('ru-RU').format(Math.round(price))
  }

  function addToCart() {
    alert(`✅ Добавлено ${basket.value.length} товаров!`)
  }

  // Возвращаем всё, включая новое поле
  return {
    // State
    userQuery,
    basket,
    loading,
    error,
    diet,
    allergies,
    originalPrice,
    totalPrice,
    agentLabel,
    parsedConstraints,  // НОВОЕ
    // Methods
    optimizeBasket,
    formatPrice,
    addToCart
  }
}
