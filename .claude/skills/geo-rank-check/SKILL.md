---
name: geo-rank-check
description: Проверка присутствия бренда или URL в ответах языковых моделей (LLM). Используйте, когда нужно узнать, упоминается ли бренд в ChatGPT, Perplexity, ЯндексGPT и других LLM по запросам; когда нужен LLM Visibility Score; когда оценивается эффективность GEO-оптимизации. Триггеры: «GEO-проверка», «видимость в ChatGPT», «проверь бренд в LLM», «llm visibility», «находят ли нас в AI-поиске», «GEO-аудит». Не используйте для классического SEO-аудита (технический, семантика, контент) — для этого есть отдельные скрипты в /root/seo/scripts/.
metadata:
  version: 1.0.0
  platform: Multi-LLM (GEOrank API / OpenAI / Perplexity / Яндекс API)
---

# GEO Rank Check — Видимость бренда в LLM

Вы — GEO-аналитик. Ваша задача — проверить, присутствует ли бренд (URL, название компании, продукт) в ответах языковых моделей на релевантные запросы.

## Два режима работы

### Режим A: GEOrank API (рекомендуемый)
Если у клиента есть доступ к [GEOrank](https://georank.ru/) (тарифы от 20 000 ₽/мес):
```bash
python3 /root/seo/skills/geo-rank-check/scripts/geo_check.py \
  --mode georank \
  --api-key $GEORANK_API_KEY \
  --brand "Название бренда" \
  --queries-file queries.csv \
  --output results.json
```

### Режим B: Прямые API (бесплатный / без GEOrank)
```bash
python3 /root/seo/skills/geo-rank-check/scripts/geo_check.py \
  --mode direct \
  --brand "Название бренда" \
  --url "https://example.com" \
  --queries-file queries.csv \
  --output results.json \
  --providers perplexity openai \
  --perplexity-key $PERPLEXITY_API_KEY \
  --openai-key $OPENAI_API_KEY
```

## Формат входного файла queries.csv

```csv
query,model,intent
"лучшие сервисы CRM для малого бизнеса",any,informing
"какой CRM выбрать для команды 10 человек",any,comparing
"название_бренда отзывы",any,branded
```

Обязательные колонки: `query`. Опциональные: `model` (perplexity/openai/gigachat/any), `intent` (informing/comparing/branded/commercial).

## Выходной JSON

```json
{
  "brand": "Example Corp",
  "checked_at": "2026-09-02T12:00:00Z",
  "total_queries": 50,
  "llm_visibility_score": 42,
  "results": [
    {
      "query": "лучшие сервисы CRM для малого бизнеса",
      "intent": "informing",
      "found": true,
      "provider": "perplexity",
      "model": "sonar",
      "position": 3,
      "context": "...Example Corp предлагает бесплатный тариф...",
      "citation_url": "https://example.com/pricing"
    }
  ],
  "summary": {
    "informing_visibility": 0.35,
    "comparing_visibility": 0.55,
    "branded_visibility": 0.80,
    "not_found": 18
  }
}
```

**LLM Visibility Score** = среднее доля присутствий, где:
- `found: false` → 0
- `found: true` → 1
Умножается на 100, округляется до целого.

## Пошаговый рабочий процесс

### Шаг 1: Собрать репрезентативные запросы

Если у проекта есть семантическое ядро (CSV), отфильтруйте:
- **Branded** — запросы с названием бренда
- **Comparing** — запросы сравнения, выбора
- **Informing** — информационные запросы без бренда

```bash
# Пример фильтрации через Python
python3 -c "
import csv, sys
reader = csv.DictReader(sys.stdin)
for row in reader:
    if row.get('intent') in ('branded','comparing','informing'):
        print(f\"{row['query']},{row.get('intent','any')},any\")
" < yadro-project.csv > queries_for_geo.csv
```

Минимум для проверки: 30 запросов (10 branded + 10 comparing + 10 informing).

### Шаг 2: Запустить проверку

```bash
python3 /root/seo/skills/geo-rank-check/scripts/geo_check.py \
  --mode direct \
  --brand "Бренд" \
  --url "https://site.ru" \
  --queries-file queries_for_geo.csv \
  --output geo-results.json \
  --providers perplexity openai
```

### Шаг 3: Прочитать результат и интерпретировать

Откройте `geo-results.json` и примените методику из [`references/methodology.md`](references/methodology.md):

| LLM Visibility Score | Значение | Рекомендация |
|---|---|---|
| 0–20 | Бренд практически невидим | Срочно: проверить индексацию, усилить внешний след (СМИ, справочники) |
| 21–40 | Слабая видимость | Сфокусироваться на Comparing-запросах, усилить E-E-A-T |
| 41–65 | Средняя видимость | Работать с Comparing и Informing, следить за динамикой |
| 66–80 | Хорошая видимость | Мониторить ежемесячно, не расслабляться |
| 81–100 | Бренд цитируется в большинстве ответов | Держать мониторинг, следить за контекстом (позитив/негатив) |

### Шаг 4: Записать результат в проект

Создать файл `<проект>/geo-visibility.md`:
```markdown
# GEO-видимость — <Бренд>

**Дата проверки:** 2026-09-02
**LLM Visibility Score:** 42/100

## Сводка по намерениям
| Тип | Видимость | Запросов |
|---|---|---|
| Branded | 80% | 10 |
| Comparing | 55% | 10 |
| Informing | 35% | 10 |

## Не найдены (приоритетные)
1. ...

## Что сделать
1. ...
```

## Методология измерения

Формула из [`references/methodology.md`](references/methodology.md):

```
видимость = (found_queries / total_queries) × 100
```

Разбивка по интентам:
- **Branded** (80%) — бренд ищут по имени → должен быть в ответе
- **Comparing** (55%) — модель выбирает сама → зависит от контента и внешнего следа
- **Informing** (35%) — самый сложный сегмент → попадание = признак качественного контента

Веса контуров: `branded × 0.2 + comparing × 0.3 + informing × 0.5`

## Провайдеры

| Провайдер | Модель по умолчанию | Стоимость | Примечание |
|---|---|---|---|
| Perplexity | `sonar` | бесплатно 100/день, Pro — безлимит | Лучший для поисковых запросов |
| OpenAI | `gpt-4o` | платно | Использовать как доп. источник |
| Яндекс API | `Pro`) | по тарифу | Для ЯндексGPT (нужен API-ключ) |

## Важные ограничения

- **Один запуск — один провайдер.** Не мешайте в одном запросе Perplexity и OpenAI: они дают разные ответы, это не ошибка.
- **Бесплатные лимиты.** Perplexity Sonar — 100 запросов/день, ставьте паузу 2 сек между запросами.
- **GEOrank приоритетнее.** Если есть доступ — используйте его, он покрывает больше моделей сразу (ChatGPT, Perplexity, GigaChat, ЯндексGPT).
- **Контекст цитирования.** Если бренд найден, но в негативном контексте — это тоже «найден». Отмечайте в `geo-results.json` поле `sentiment`.

## Ошибки и решения

| Ошибка | Причина | Решение |
|---|---|---|
| `API key not found` | Ключ не установлен | Экспортировать: `export PERPLEXITY_API_KEY=...` |
| `Rate limit exceeded` | Лимит API | Добавить `--delay 3` (пауза между запросами) |
| `No results for query` | Пустой ответ модели | Норма — пропускать, не считать ошибкой |
| `georank: 401 Unauthorized` | Неверный API-ключ | Проверить ключ в https://lk.georank.ru/ |
| Timeout | Модель долго отвечает | Увеличить `--timeout 60` |

## Команды агента

- «Проверь GEO-видимость [бренда] по запросам из [файла]»
- «Сделай GEO-аудит [URL]»
- «GEO-чек для клиента [название]»
- «Запусти geo-rank-check на [список запросов]»
