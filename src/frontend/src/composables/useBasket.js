// src/frontend/src/composables/useBasket.js
import { ref, computed } from 'vue'

export function useBasket() {
  // ========== STATE ==========
  const userQuery = ref('')
  const basket = ref([])
  const loading = ref(false)
  const error = ref(null)
  
  const diet = ref('любая')
  const allergies = ref('')
  
  const parsedConstraints = ref(null)
  const originalPrice = ref(0)
  
  // Этапы работы агентов
  const stages = ref([])
  
  // ========== COMPUTED ==========
  const totalPrice = computed(() => 
    basket.value.reduce((sum, item) => sum + (item.price || 0), 0)
  )
  
  const agentLabel = {
    'compatibility': '🔗 Совместимость',
    'budget': '💰 Бюджет',
    'profile': '👤 Профиль',
    'llm_parser': '🧠 LLM Parser'
  }
  
  // ========== METHODS ==========
  async function optimizeBasket() {
    if (!userQuery.value.trim()) {
      error.value = '⚠️ Введите запрос!'
      basket.value = []
      parsedConstraints.value = null
      stages.value = []
      return
    }
    
    loading.value = true
    error.value = null
    basket.value = []
    parsedConstraints.value = null
    stages.value = []
    
    try {
      const response = await fetch('http://localhost:5000/api/generate-basket', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query: userQuery.value })
      })
      
      if (!response.ok) {
        throw new Error(`Server error ${response.status}`)
      }
      
      const data = await response.json()
      
      console.log('📦 Backend response:', data)  // ✅ DEBUG
      
      if (data.status === 'success') {
        basket.value = data.basket || []
        parsedConstraints.value = data.parsed
        originalPrice.value = data.summary?.original_price || 0
        
        // ✅ ИСПРАВЛЕНО: Нормализуем stages
        stages.value = normalizeStages(data.stages || [])
        
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
  
  // ✅ НОВАЯ ФУНКЦИЯ: Нормализация stages
  function normalizeStages(stages) {
    return stages.map(stage => {
      const normalized = { ...stage }
      
      // Если compatibility_score это объект - извлекаем total_score
      if (stage.result?.compatibility_score) {
        const score = stage.result.compatibility_score
        normalized.result = {
          ...stage.result,
          compatibility_score: typeof score === 'object' 
            ? score.total_score 
            : score
        }
      }
      
      return normalized
    })
  }
  
  function formatPrice(price) {
    return new Intl.NumberFormat('ru-RU').format(Math.round(price))
  }
  
  function addToCart() {
    alert(`✅ Добавлено ${basket.value.length} товаров!`)
  }
  
  return {
    // State
    userQuery,
    basket,
    loading,
    error,
    diet,
    allergies,
    parsedConstraints,
    originalPrice,
    totalPrice,
    stages,
    
    // Constants
    agentLabel,
    
    // Methods
    optimizeBasket,
    formatPrice,
    addToCart
  }
}
