const API_URL = '/api/generate-basket';

// --- DOM-узлы ---
const btnGenerate    = document.getElementById('btn-generate');
const queryInput     = document.getElementById('query');
const dietSelect     = document.getElementById('diet');
const allergiesInput = document.getElementById('allergies');

const placeholder    = document.getElementById('result-placeholder');
const content        = document.getElementById('result-content');
const errorBlock     = document.getElementById('result-error');
const loadingBlock   = document.getElementById('result-loading');

const metaScenario   = document.getElementById('meta-scenario');
const metaScore      = document.getElementById('meta-score');
const metaTotal      = document.getElementById('meta-total');
const basketBody     = document.getElementById('basket-body');
const budgetWarning  = document.getElementById('budget-warning');
const errorMessage   = document.getElementById('error-message');

// --- Утилиты ---
function show(el) { el.classList.remove('hidden'); }
function hide(el) { el.classList.add('hidden'); }

function setState(state) {
  hide(placeholder); hide(content); hide(errorBlock); hide(loadingBlock);
  if (state === 'loading') show(loadingBlock);
  if (state === 'result')  show(content);
  if (state === 'error')   show(errorBlock);
  if (state === 'empty')   show(placeholder);
}

// --- Разбираем структуру ответа пайплайна ---
function extractBasketData(data) {
  const basket   = data.basket   || [];
  const stages   = data.stages   || [];
  const summary  = data.summary  || {};
  const metadata = data.metadata || {};

  const compatStage  = stages.find(s => s.agent === 'compatibility') || {};
  const compatResult = compatStage.result || {};

  return {
    basket,
    total_price:         summary.total_price || 0,
    original_price:      summary.original_price || 0,
    savings:             summary.savings || 0,
    scenario_used:       { name: metadata.scenario_used || '—' },
    compatibility_score: compatResult.compatibility_score || 0,
    within_budget:       summary.within_budget ?? true,
    budget_rub:          summary.budget_rub || null,
    people:              metadata.people || 1
  };
}

// --- Лог агентов ---
function renderAgentLog(data) {
  const logBody = document.getElementById('agent-log-body');
  if (!logBody) return;

  const stages = data.stages || [];
  if (!stages.length) {
    logBody.innerHTML = '<p class="log-empty">Нет данных о работе агентов</p>';
    return;
  }

  logBody.innerHTML = stages.map(stage => {
    const result   = stage.result || {};
    const status   = stage.status === 'completed' ? '✅' : '❌';
    const duration = stage.duration ? `${stage.duration}с` : '';

    let detail = '';

    if (stage.agent === 'llm_parser') {
      const p = result.parsed || {};
      detail = [
        p.budget_rub            ? `💰 Бюджет: ${p.budget_rub}₽`              : '',
        p.people                ? `👥 Людей: ${p.people}`                      : '',
        p.meal_type?.length     ? `🍽 Тип: ${p.meal_type.join(', ')}`          : '',
        p.prefer_quick          ? `⚡ Быстро`                                  : '',
        p.exclude_tags?.length  ? `🚫 Исключить: ${p.exclude_tags.join(', ')}` : ''
      ].filter(Boolean).join(' · ');
    }

    if (stage.agent === 'compatibility') {
      const basket   = result.basket   || [];
      const scenario = result.scenario || {};
      detail = [
        scenario.name              ? `📋 Сценарий: ${scenario.name}`                     : '',
        basket.length              ? `🛒 Найдено товаров: ${basket.length}`               : '',
        result.total_price         ? `💵 Сумма: ${result.total_price.toFixed(2)}₽`        : '',
        result.compatibility_score ? `⭐ Score: ${result.compatibility_score}`             : ''
      ].filter(Boolean).join(' · ');
    }

    if (stage.agent === 'budget') {
      const replacements = result.replacements || [];
    if (replacements.length > 0) {
        const replStr = replacements.map(r =>
        `<div class="log-replacement">↩ <b>${r.from}</b> → <b>${r.to}</b> (−${r.saved?.toFixed(2)}₽)</div>`
        ).join('');
        detail = `💡 Замен: ${replacements.length}, сэкономлено: ${result.saved?.toFixed(2)}₽${replStr}`;
    } else {
        detail = result.within_budget
        ? '✅ Бюджет не превышен, замены не нужны'
        : '⚠️ Не удалось уложиться в бюджет';
    }
    }

    if (stage.agent === 'profile') {
      detail = '⏳ Персонализация в разработке';
    }

    return `
      <div class="log-stage">
        <div class="log-stage-header">
          <span class="log-status">${status}</span>
          <span class="log-name">${stage.name}</span>
          <span class="log-duration">${duration}</span>
        </div>
        ${detail ? `<div class="log-detail">${detail}</div>` : ''}
      </div>
    `;
  }).join('');
}

// --- Рендер корзины ---
function renderBasket(extracted, rawData) {
  const { basket, total_price, scenario_used, compatibility_score, within_budget, budget_rub } = extracted;

  if (!basket || basket.length === 0) {
    errorMessage.textContent = '❌ Корзина пустая — попробуй другой запрос или увеличь бюджет';
    setState('error');
    return;
  }

  metaScenario.textContent = `📋 ${scenario_used?.name || 'Сценарий не определён'}`;
  metaScore.textContent    = `⭐ Совместимость: ${compatibility_score}`;
  metaTotal.textContent    = `💰 Итого: ${Number(total_price).toFixed(2)} ₽`;

  if (budget_rub) {
    within_budget ? hide(budgetWarning) : show(budgetWarning);
  }

  basketBody.innerHTML = basket.map(item => `
    <tr>
      <td class="name">${item.name || '—'}</td>
      <td class="role">${item.ingredient_role || '—'}</td>
      <td>${Number(item.quantity).toFixed(2)} ${item.unit || ''}</td>
      <td>${Number(item.price_per_unit).toFixed(2)} ₽</td>
      <td class="price">${Number(item.total_price).toFixed(2)} ₽</td>
    </tr>
  `).join('');

  // ✅ Лог агентов рендерится здесь — rawData гарантированно определена
  renderAgentLog(rawData);

  setState('result');
}

// --- Запрос к API ---
async function generateBasket() {
  const query = queryInput.value.trim();
  if (!query) { queryInput.focus(); return; }

  setState('loading');
  btnGenerate.disabled = true;

  try {
    const response = await fetch(API_URL, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ query })
    });

    const data = await response.json();

    if (!response.ok || data.status === 'error') {
      throw new Error(data.message || `HTTP ${response.status}`);
    }

    const extracted = extractBasketData(data);
    renderBasket(extracted, data);  // ✅ data передаётся как rawData

  } catch (err) {
    errorMessage.textContent = `❌ ${err.message}`;
    setState('error');
  } finally {
    // ✅ Только разблокируем кнопку — больше ничего
    btnGenerate.disabled = false;
  }
}

// --- События ---
btnGenerate.addEventListener('click', generateBasket);
queryInput.addEventListener('keydown', e => {
  if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); generateBasket(); }
});
